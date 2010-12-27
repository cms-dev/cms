/*
 *	A Simple Sandbox for Moe
 *
 *	Copyright (c) 2001--2010 Martin Mares <mj@ucw.cz>
 *  Copyright (c) 2010 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
 */

#define _LARGEFILE64_SOURCE
#define _GNU_SOURCE

#include "autoconf.h"

#include <errno.h>
#include <stdio.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <stdint.h>
#include <unistd.h>
#include <getopt.h>
#include <time.h>
#include <sys/wait.h>
#include <sys/user.h>
#include <sys/time.h>
#include <sys/ptrace.h>
#include <sys/signal.h>
#include <sys/sysinfo.h>
#include <sys/resource.h>
#include <sys/utsname.h>
#include <linux/ptrace.h>

#if defined(CONFIG_BOX_KERNEL_AMD64) && !defined(CONFIG_BOX_USER_AMD64)
#include <asm/unistd_32.h>
#define NATIVE_NR_execve 59		/* 64-bit execve */
#else
#include <asm/unistd.h>
#define NATIVE_NR_execve __NR_execve
#endif

#define NONRET __attribute__((noreturn))
#define UNUSED __attribute__((unused))
#define ARRAY_SIZE(a) (int)(sizeof(a)/sizeof(a[0]))

static int filter_syscalls;		/* 0=off, 1=liberal, 2=totalitarian */
static int timeout;			/* milliseconds */
static int wall_timeout;
static int extra_timeout;
static int pass_environ;
static int file_access;
static int verbose;
static int memory_limit;
static int stack_limit;
static char *redir_stdin, *redir_stdout, *redir_stderr;
static char *set_cwd;

static pid_t box_pid;
static int is_ptraced;
static volatile int timer_tick;
static struct timeval start_time;
static int ticks_per_sec;
static int exec_seen;
static int partial_line;

static int mem_peak_kb;
static int total_ms, wall_ms;

static void die(char *msg, ...) NONRET;
static void sample_mem_peak(void);

/*** Meta-files ***/

static FILE *metafile;

static void
meta_open(const char *name)
{
  if (!strcmp(name, "-"))
    {
      metafile = stdout;
      return;
    }
  metafile = fopen(name, "w");
  if (!metafile)
    die("Failed to open metafile '%s'",name);
}

static void
meta_close(void)
{
  if (metafile && metafile != stdout)
    fclose(metafile);
}

static void __attribute__((format(printf,1,2)))
meta_printf(const char *fmt, ...)
{
  if (!metafile)
    return;

  va_list args;
  va_start(args, fmt);
  vfprintf(metafile, fmt, args);
  va_end(args);
}

static void
final_stats(struct rusage *rus)
{
  struct timeval total, now, wall;
  timeradd(&rus->ru_utime, &rus->ru_stime, &total);
  total_ms = total.tv_sec*1000 + total.tv_usec/1000;
  gettimeofday(&now, NULL);
  timersub(&now, &start_time, &wall);
  wall_ms = wall.tv_sec*1000 + wall.tv_usec/1000;

  meta_printf("time:%d.%03d\n", total_ms/1000, total_ms%1000);
  meta_printf("time-wall:%d.%03d\n", wall_ms/1000, wall_ms%1000);
  meta_printf("mem:%llu\n", (unsigned long long) mem_peak_kb * 1024);
}

/*** Messages and exits ***/

static void NONRET
box_exit(int rc)
{
  if (box_pid > 0)
    {
      sample_mem_peak();
      if (is_ptraced)
	ptrace(PTRACE_KILL, box_pid);
      kill(-box_pid, SIGKILL);
      kill(box_pid, SIGKILL);
      meta_printf("killed:1\n");

      struct rusage rus;
      int p, stat;
      do
	p = wait4(box_pid, &stat, 0, &rus);
      while (p < 0 && errno == EINTR);
      if (p < 0)
	fprintf(stderr, "UGH: Lost track of the process (%m)\n");
      else
	final_stats(&rus);
    }
  meta_close();
  exit(rc);
}

static void
flush_line(void)
{
  if (partial_line)
    fputc('\n', stderr);
  partial_line = 0;
}

/* Report an error of the sandbox itself */
static void NONRET __attribute__((format(printf,1,2)))
die(char *msg, ...)
{
  va_list args;
  va_start(args, msg);
  flush_line();
  char buf[1024];
  vsnprintf(buf, sizeof(buf), msg, args);
  meta_printf("status:XX\nmessage:%s\n", buf);
  fputs(buf, stderr);
  fputc('\n', stderr);
  box_exit(2);
}

/* Report an error of the program inside the sandbox */
static void NONRET __attribute__((format(printf,1,2)))
err(char *msg, ...)
{
  va_list args;
  va_start(args, msg);
  flush_line();
  if (msg[0] && msg[1] && msg[2] == ':' && msg[3] == ' ')
    {
      meta_printf("status:%c%c\n", msg[0], msg[1]);
      msg += 4;
    }
  char buf[1024];
  vsnprintf(buf, sizeof(buf), msg, args);
  meta_printf("message:%s\n", buf);
  fputs(buf, stderr);
  fputc('\n', stderr);
  box_exit(1);
}

/* Write a message, but only if in verbose mode */
static void __attribute__((format(printf,1,2)))
msg(char *msg, ...)
{
  va_list args;
  va_start(args, msg);
  if (verbose)
    {
      int len = strlen(msg);
      if (len > 0)
        partial_line = (msg[len-1] != '\n');
      vfprintf(stderr, msg, args);
      fflush(stderr);
    }
  va_end(args);
}

static void *
xmalloc(size_t size)
{
  void *p = malloc(size);
  if (!p)
    die("Out of memory");
  return p;
}

/*** Syscall rules ***/

static const char * const syscall_names[] = {
#include "syscall-table.h"
};
#define NUM_SYSCALLS ARRAY_SIZE(syscall_names)
#define NUM_ACTIONS (NUM_SYSCALLS+64)

enum action {
  A_DEFAULT,		// Use the default action
  A_NO,			// Always forbid
  A_YES,		// Always permit
  A_FILENAME,		// Permit if arg1 is a known filename
  A_ACTION_MASK = 15,
  A_NO_RETVAL = 32,	// Does not return a value
  A_SAMPLE_MEM = 64,	// Sample memory usage before the syscall
  A_LIBERAL = 128,	// Valid only in liberal mode
  // Must fit in a unsigned char
};

static unsigned char syscall_action[NUM_ACTIONS] = {
#define S(x) [__NR_##x]

    // Syscalls permitted for specific file names
    S(open) = A_FILENAME,
    S(creat) = A_FILENAME,
    S(unlink) = A_FILENAME,
    S(access) = A_FILENAME,			
    S(truncate) = A_FILENAME,
    S(stat) = A_FILENAME,
    S(lstat) = A_FILENAME,
    S(readlink) = A_FILENAME,
#ifndef CONFIG_BOX_USER_AMD64
    S(oldstat) = A_FILENAME,
    S(oldlstat) = A_FILENAME,
    S(truncate64) = A_FILENAME,
    S(stat64) = A_FILENAME,
    S(lstat64) = A_FILENAME,
#endif

    // Syscalls permitted always
    S(exit) = A_YES | A_SAMPLE_MEM,
    S(read) = A_YES,
    S(write) = A_YES,
    S(close) = A_YES,
    S(lseek) = A_YES,
    S(getpid) = A_YES,
    S(getuid) = A_YES,
    S(dup) = A_YES,
    S(brk) = A_YES,
    S(getgid) = A_YES,
    S(geteuid) = A_YES,
    S(getegid) = A_YES,
    S(dup2) = A_YES,
    S(ftruncate) = A_YES,
    S(fstat) = A_YES,
    S(personality) = A_YES,
    S(readv) = A_YES,
    S(writev) = A_YES,
    S(getresuid) = A_YES,
#ifdef __NR_pread64
    S(pread64) = A_YES,
    S(pwrite64) = A_YES,
#else
    S(pread) = A_YES,
    S(pwrite) = A_YES,
#endif
    S(fcntl) = A_YES,
    S(mmap) = A_YES,
    S(munmap) = A_YES,
    S(ioctl) = A_YES,
    S(uname) = A_YES,
    S(gettid) = A_YES,
    S(set_thread_area) = A_YES,
    S(get_thread_area) = A_YES,
    S(set_tid_address) = A_YES,
    S(exit_group) = A_YES | A_SAMPLE_MEM,
#ifdef CONFIG_BOX_USER_AMD64
    S(arch_prctl) = A_YES,
#else
    S(oldfstat) = A_YES,
    S(ftruncate64) = A_YES,
    S(_llseek) = A_YES,
    S(fstat64) = A_YES,
    S(fcntl64) = A_YES,
    S(mmap2) = A_YES,
#endif

    // Syscalls permitted only in liberal mode
    S(time) = A_YES | A_LIBERAL,
    S(alarm) = A_YES | A_LIBERAL,
    S(pause) = A_YES | A_LIBERAL,
    S(fchmod) = A_YES | A_LIBERAL,
    S(getrlimit) = A_YES | A_LIBERAL,
    S(getrusage) = A_YES | A_LIBERAL,
    S(gettimeofday) = A_YES | A_LIBERAL,
    S(select) = A_YES | A_LIBERAL,
    S(setitimer) = A_YES | A_LIBERAL,
    S(getitimer) = A_YES | A_LIBERAL,
    S(mprotect) = A_YES | A_LIBERAL,
    S(getdents) = A_YES | A_LIBERAL,
    S(getdents64) = A_YES | A_LIBERAL,
    S(fdatasync) = A_YES | A_LIBERAL,
    S(mremap) = A_YES | A_LIBERAL,
    S(poll) = A_YES | A_LIBERAL,
    S(getcwd) = A_YES | A_LIBERAL,
    S(nanosleep) = A_YES | A_LIBERAL,
    S(rt_sigreturn) = A_YES | A_LIBERAL | A_NO_RETVAL,
    S(rt_sigaction) = A_YES | A_LIBERAL,
    S(rt_sigprocmask) = A_YES | A_LIBERAL,
    S(rt_sigpending) = A_YES | A_LIBERAL,
    S(rt_sigtimedwait) = A_YES | A_LIBERAL,
    S(rt_sigqueueinfo) = A_YES | A_LIBERAL,
    S(rt_sigsuspend) = A_YES | A_LIBERAL,
    S(_sysctl) = A_YES | A_LIBERAL,
#ifndef CONFIG_BOX_USER_AMD64
    S(sigaction) = A_YES | A_LIBERAL,
    S(sgetmask) = A_YES | A_LIBERAL,
    S(ssetmask) = A_YES | A_LIBERAL,
    S(sigsuspend) = A_YES | A_LIBERAL,
    S(sigpending) = A_YES | A_LIBERAL,
    S(sigreturn) = A_YES | A_LIBERAL | A_NO_RETVAL,
    S(sigprocmask) = A_YES | A_LIBERAL,
    S(ugetrlimit) = A_YES | A_LIBERAL,
    S(readdir) = A_YES | A_LIBERAL,
    S(signal) = A_YES | A_LIBERAL,
    S(_newselect) = A_YES | A_LIBERAL,
#endif

#undef S
};

static const char *
syscall_name(unsigned int id, char *buf)
{
  if (id < NUM_SYSCALLS && syscall_names[id])
    return syscall_names[id];
  else
    {
      sprintf(buf, "#%d", id);
      return buf;
    }
}

static int
syscall_by_name(char *name)
{
  for (unsigned int i=0; i<NUM_SYSCALLS; i++)
    if (syscall_names[i] && !strcmp(syscall_names[i], name))
      return i;
  if (name[0] == '#')
    name++;
  if (!*name)
    return -1;
  char *ep;
  unsigned long l = strtoul(name, &ep, 0);
  if (*ep)
    return -1;
  if (l >= NUM_ACTIONS)
    return NUM_ACTIONS;
  return l;
}

static int
set_syscall_action(char *a)
{
  char *sep = strchr(a, '=');
  enum action act = A_YES;
  if (sep)
    {
      *sep++ = 0;
      if (!strcmp(sep, "yes"))
	act = A_YES;
      else if (!strcmp(sep, "no"))
	act = A_NO;
      else if (!strcmp(sep, "file"))
	act = A_FILENAME;
      else
	return 0;
    }

  int sys = syscall_by_name(a);
  if (sys < 0)
    die("Unknown syscall `%s'", a);
  if (sys >= NUM_ACTIONS)
    die("Syscall `%s' out of range", a);
  syscall_action[sys] = act;
  return 1;
}

/*** Path rules ***/

struct path_rule {
  char *path;
  enum action action;
  struct path_rule *next;
};

static struct path_rule default_path_rules[] = {
  { "/etc/", A_YES },
  { "/lib/", A_YES },
  { "/usr/lib/", A_YES },
  { "/opt/lib/", A_YES },
  { "/usr/share/zoneinfo/", A_YES },
  { "/usr/share/locale/", A_YES },
  { "/dev/null", A_YES },
  { "/dev/zero", A_YES },
  { "/proc/meminfo", A_YES },
  { "/proc/self/stat", A_YES },
  { "/proc/self/exe", A_YES },			// Needed by FPC 2.0.x runtime
};

static struct path_rule *user_path_rules;
static struct path_rule **last_path_rule = &user_path_rules;

static int
set_path_action(char *a)
{
  char *sep = strchr(a, '=');
  enum action act = A_YES;
  if (sep)
    {
      *sep++ = 0;
      if (!strcmp(sep, "yes"))
	act = A_YES;
      else if (!strcmp(sep, "no"))
	act = A_NO;
      else
	return 0;
    }

  struct path_rule *r = xmalloc(sizeof(*r) + strlen(a) + 1);
  r->path = (char *)(r+1);
  strcpy(r->path, a);
  r->action = act;
  r->next = NULL;
  *last_path_rule = r;
  last_path_rule = &r->next;
  return 1;
}

static enum action
match_path_rule(struct path_rule *r, char *path)
{
  char *rr = r->path;
  while (*rr)
    if (*rr++ != *path++)
      {
	if (rr[-1] == '/' && !path[-1])
	  break;
	return A_DEFAULT;
      }
  if (rr > r->path && rr[-1] != '/' && *path)
    return A_DEFAULT;
  return r->action;
}

/*** Environment rules ***/

struct env_rule {
  char *var;			// Variable to match
  char *val;			// ""=clear, NULL=inherit
  int var_len;
  struct env_rule *next;
};

static struct env_rule *first_env_rule;
static struct env_rule **last_env_rule = &first_env_rule;

static struct env_rule default_env_rules[] = {
  { "LIBC_FATAL_STDERR_", "1" }
};

static int
set_env_action(char *a0)
{
  struct env_rule *r = xmalloc(sizeof(*r) + strlen(a0) + 1);
  char *a = (char *)(r+1);
  strcpy(a, a0);

  char *sep = strchr(a, '=');
  if (sep == a)
    return 0;
  r->var = a;
  if (sep)
    {
      *sep++ = 0;
      r->val = sep;
    }
  else
    r->val = NULL;
  *last_env_rule = r;
  last_env_rule = &r->next;
  r->next = NULL;
  return 1;
}

static int
match_env_var(char *env_entry, struct env_rule *r)
{
  if (strncmp(env_entry, r->var, r->var_len))
    return 0;
  return (env_entry[r->var_len] == '=');
}

static void
apply_env_rule(char **env, int *env_sizep, struct env_rule *r)
{
  // First remove the variable if already set
  int pos = 0;
  while (pos < *env_sizep && !match_env_var(env[pos], r))
    pos++;
  if (pos < *env_sizep)
    {
      (*env_sizep)--;
      env[pos] = env[*env_sizep];
      env[*env_sizep] = NULL;
    }

  // What is the new value?
  char *new;
  if (r->val)
    {
      if (!r->val[0])
	return;
      new = xmalloc(r->var_len + 1 + strlen(r->val) + 1);
      sprintf(new, "%s=%s", r->var, r->val);
    }
  else
    {
      pos = 0;
      while (environ[pos] && !match_env_var(environ[pos], r))
	pos++;
      if (!(new = environ[pos]))
	return;
    }

  // Add it at the end of the array
  env[(*env_sizep)++] = new;
  env[*env_sizep] = NULL;
}

static char **
setup_environment(void)
{
  // Link built-in rules with user rules
  for (int i=ARRAY_SIZE(default_env_rules)-1; i >= 0; i--)
    {
      default_env_rules[i].next = first_env_rule;
      first_env_rule = &default_env_rules[i];
    }

  // Scan the original environment
  char **orig_env = environ;
  int orig_size = 0;
  while (orig_env[orig_size])
    orig_size++;

  // For each rule, reserve one more slot and calculate length
  int num_rules = 0;
  for (struct env_rule *r = first_env_rule; r; r=r->next)
    {
      num_rules++;
      r->var_len = strlen(r->var);
    }

  // Create a new environment
  char **env = xmalloc((orig_size + num_rules + 1) * sizeof(char *));
  int size;
  if (pass_environ)
    {
      memcpy(env, environ, orig_size * sizeof(char *));
      size = orig_size;
    }
  else
    size = 0;
  env[size] = NULL;

  // Apply the rules one by one
  for (struct env_rule *r = first_env_rule; r; r=r->next)
    apply_env_rule(env, &size, r);

  // Return the new env and pass some gossip
  if (verbose > 1)
    {
      fprintf(stderr, "Passing environment:\n");
      for (int i=0; env[i]; i++)
	fprintf(stderr, "\t%s\n", env[i]);
    }
  return env;
}

/*** Low-level parsing of syscalls ***/

#ifdef CONFIG_BOX_KERNEL_AMD64
typedef uint64_t arg_t;
#else
typedef uint32_t arg_t;
#endif

struct syscall_args {
  arg_t sys;
  arg_t arg1, arg2, arg3;
  arg_t result;
  struct user user;
};

static int read_user_mem(arg_t addr, char *buf, int len)
{
  static int mem_fd;

  if (!mem_fd)
    {
      char memname[64];
      sprintf(memname, "/proc/%d/mem", (int) box_pid);
      mem_fd = open(memname, O_RDONLY);
      if (mem_fd < 0)
	die("open(%s): %m", memname);
    }
  if (lseek64(mem_fd, addr, SEEK_SET) < 0)
    die("lseek64(mem): %m");
  return read(mem_fd, buf, len);
}

#ifdef CONFIG_BOX_KERNEL_AMD64

static void
get_syscall_args(struct syscall_args *a, int is_exit)
{
  if (ptrace(PTRACE_GETREGS, box_pid, NULL, &a->user) < 0)
    die("ptrace(PTRACE_GETREGS): %m");
  a->sys = a->user.regs.orig_rax;
  a->result = a->user.regs.rax;

  /*
   *  CAVEAT: We have to check carefully that this is a real 64-bit syscall.
   *  We test whether the process runs in 64-bit mode, but surprisingly this
   *  is not enough: a 64-bit process can still issue the INT 0x80 instruction
   *  which performs a 32-bit syscall. Currently, the only known way how to
   *  detect this situation is to inspect the instruction code (the kernel
   *  keeps a syscall type flag internally, but it is not accessible from
   *  user space). Hopefully, there is no instruction whose suffix is the
   *  code of the SYSCALL instruction. Sometimes, one would wish the
   *  instruction codes to be unique even when read backwards :)
   */

  if (is_exit)
    return;

  int sys_type;
  uint16_t instr;

  switch (a->user.regs.cs)
    {
    case 0x23:
      // 32-bit CPU mode => only 32-bit syscalls can be issued
      sys_type = 32;
      break;
    case 0x33:
      // 64-bit CPU mode
      if (read_user_mem(a->user.regs.rip-2, (char *) &instr, 2) != 2)
	err("FO: Cannot read syscall instruction, errno = %d", errno);
      switch (instr)
	{
	case 0x050f:
	  break;
	case 0x80cd:
	  err("FO: Forbidden 32-bit syscall in 64-bit mode");
	default:
	  err("XX: Unknown syscall instruction %04x", instr);
	}
      sys_type = 64;
      break;
    default:
      err("XX: Unknown code segment %04jx", (intmax_t) a->user.regs.cs);
    }

#ifdef CONFIG_BOX_USER_AMD64
  if (sys_type != 64)
    err("FO: Forbidden %d-bit mode syscall", sys_type);
#else
  if (sys_type != (exec_seen ? 32 : 64))
    err("FO: Forbidden %d-bit mode syscall", sys_type);
#endif

  if (sys_type == 32)
    {
      a->arg1 = a->user.regs.rbx;
      a->arg2 = a->user.regs.rcx;
      a->arg3 = a->user.regs.rdx;
    }
  else
    {
      a->arg1 = a->user.regs.rdi;
      a->arg2 = a->user.regs.rsi;
      a->arg3 = a->user.regs.rdx;
    }
}

static void
set_syscall_nr(struct syscall_args *a, arg_t sys)
{
  a->sys = sys;
  a->user.regs.orig_rax = sys;
  if (ptrace(PTRACE_SETREGS, box_pid, NULL, &a->user) < 0)
    die("ptrace(PTRACE_SETREGS): %m");
}

static void
sanity_check(void)
{
}

#else

static void
get_syscall_args(struct syscall_args *a, int is_exit UNUSED)
{
  if (ptrace(PTRACE_GETREGS, box_pid, NULL, &a->user) < 0)
    die("ptrace(PTRACE_GETREGS): %m");
  a->sys = a->user.regs.orig_eax;
  a->arg1 = a->user.regs.ebx;
  a->arg2 = a->user.regs.ecx;
  a->arg3 = a->user.regs.edx;
  a->result = a->user.regs.eax;
}

static void
set_syscall_nr(struct syscall_args *a, arg_t sys)
{
  a->sys = sys;
  a->user.regs.orig_eax = sys;
  if (ptrace(PTRACE_SETREGS, box_pid, NULL, &a->user) < 0)
    die("ptrace(PTRACE_SETREGS): %m");
}

static void
sanity_check(void)
{
#if !defined(CONFIG_BOX_ALLOW_INSECURE)
  struct utsname uts;
  if (uname(&uts) < 0)
    die("uname() failed: %m");

  if (!strcmp(uts.machine, "x86_64"))
    die("Running 32-bit sandbox on 64-bit kernels is inherently unsafe. Please get a 64-bit version.");
#endif
}

#endif

/*** Syscall checks ***/

typedef enum {
  S_START,
  S_CONT
} State;

static void
resolv_filename(char *namebuf) {
  if (namebuf[0] != '/') return;
  int i = 0, j = 0;
  State st = S_CONT;
  while (namebuf[i] != 0) {
    char tmp = namebuf[i];
    if (tmp == '/') {
      if (st == S_CONT) {
        st = S_START;
        namebuf[j] = tmp;
        i++;
        j++;
      } else {
        i++;
      }
    } else if (tmp == '.') {
      if (st == S_START && namebuf[i+1] == '.' && (namebuf[i+2] == '/' || namebuf[i+2] == 0)) {
        i += 2;
        if (j > 1) {
          j -= 2;
          for ( ; namebuf[j] != '/'; j--);
          st = S_CONT;
        } else {
          st = S_START;
        }
      } else {
        st = S_CONT;
        namebuf[j] = tmp;
        i++;
        j++;
      }
    } else {
      st = S_CONT;
      namebuf[j] = tmp;
      i++;
      j++;
    }
  }
  namebuf[j] = 0;
}

static void
valid_filename(arg_t addr)
{
  char namebuf[4096], *p, *end;

  if (!file_access)
    err("FA: File access forbidden");
  if (file_access >= 9)
    return;

  p = end = namebuf;
  do
    {
      if (p >= end)
	{
	  int remains = PAGE_SIZE - (addr & (PAGE_SIZE-1));
	  int l = namebuf + sizeof(namebuf) - end;
	  if (l > remains)
	    l = remains;
	  if (!l)
	    err("FA: Access to file with name too long");
	  remains = read_user_mem(addr, end, l);
	  if (remains < 0)
	    die("read(mem): %m");
	  if (!remains)
	    err("FA: Access to file with name out of memory");
	  end += remains;
	  addr += remains;
	}
    }
  while (*p++);

  msg("[%s] ", namebuf);
  if (file_access >= 4)
    return;

  // Everything in current directory is permitted
  if (file_access >= 2 && !strchr(namebuf, '/') && strcmp(namebuf, ".."))
    return;

  // Resolv the ".." for the other tests; fail if ".." is in a relative path
  enum action act = A_DEFAULT;
  resolv_filename(namebuf);
  if (strstr(namebuf, ".."))
    act = A_NO;

  // Scan user rules
  for (struct path_rule *r = user_path_rules; r && !act; r=r->next)
    act = match_path_rule(r, namebuf);

  // Scan built-in rules
  if (file_access >= 3)
    for (int i=0; i<ARRAY_SIZE(default_path_rules) && !act; i++)
      act = match_path_rule(&default_path_rules[i], namebuf);

  if (act != A_YES)
    err("FA: Forbidden access to file `%s'", namebuf);
}

// Check syscall. If invalid, return -1, otherwise return the action mask.
static int
valid_syscall(struct syscall_args *a)
{
  unsigned int sys = a->sys;
  unsigned int act = (sys < NUM_ACTIONS) ? syscall_action[sys] : A_DEFAULT;

  if (act & A_LIBERAL)
    {
      if (filter_syscalls != 1)
        act = A_DEFAULT;
    }

  switch (act & A_ACTION_MASK)
    {
    case A_YES:
      return act;
    case A_NO:
      return -1;
    case A_FILENAME:
      valid_filename(a->arg1);
      return act;
    default: ;
    }

  switch (sys)
    {
    case __NR_kill:
      if (a->arg1 == (arg_t) box_pid)
	{
	  meta_printf("exitsig:%d\n", (int) a->arg2);
	  err("SG: Committed suicide by signal %d", (int) a->arg2);
	}
      return -1;
    case __NR_tgkill:
      if (a->arg1 == (arg_t) box_pid && a->arg2 == (arg_t) box_pid)
	{
	  meta_printf("exitsig:%d\n", (int) a->arg3);
	  err("SG: Committed suicide by signal %d", (int) a->arg3);
	}
      return -1;
    default:
      return -1;
    }
}

static void
signal_alarm(int unused UNUSED)
{
  /* Time limit checks are synchronous, so we only schedule them there. */
  timer_tick = 1;
  alarm(1);
}

static void
signal_int(int unused UNUSED)
{
  /* Interrupts are fatal, so no synchronization requirements. */
  meta_printf("exitsig:%d\n", SIGINT);
  err("SG: Interrupted");
}

#define PROC_BUF_SIZE 4096
static void
read_proc_file(char *buf, char *name, int *fdp)
{
  int c;

  if (!*fdp)
    {
      sprintf(buf, "/proc/%d/%s", (int) box_pid, name);
      *fdp = open(buf, O_RDONLY);
      if (*fdp < 0)
	die("open(%s): %m", buf);
    }
  lseek(*fdp, 0, SEEK_SET);
  if ((c = read(*fdp, buf, PROC_BUF_SIZE-1)) < 0)
    die("read on /proc/$pid/%s: %m", name);
  if (c >= PROC_BUF_SIZE-1)
    die("/proc/$pid/%s too long", name);
  buf[c] = 0;
}

static void
check_timeout(void)
{
  if (wall_timeout)
    {
      struct timeval now, wall;
      int wall_ms;
      gettimeofday(&now, NULL);
      timersub(&now, &start_time, &wall);
      wall_ms = wall.tv_sec*1000 + wall.tv_usec/1000;
      if (wall_ms > wall_timeout)
        err("TO: Time limit exceeded (wall clock)");
      if (verbose > 1)
        fprintf(stderr, "[wall time check: %d msec]\n", wall_ms);
    }
  if (timeout)
    {
      char buf[PROC_BUF_SIZE], *x;
      int utime, stime, ms;
      static int proc_stat_fd;
      read_proc_file(buf, "stat", &proc_stat_fd);
      x = buf;
      while (*x && *x != ' ')
	x++;
      while (*x == ' ')
	x++;
      if (*x++ != '(')
	die("proc stat syntax error 1");
      while (*x && (*x != ')' || x[1] != ' '))
	x++;
      while (*x == ')' || *x == ' ')
	x++;
      if (sscanf(x, "%*c %*d %*d %*d %*d %*d %*d %*d %*d %*d %*d %d %d", &utime, &stime) != 2)
	die("proc stat syntax error 2");
      ms = (utime + stime) * 1000 / ticks_per_sec;
      if (verbose > 1)
	fprintf(stderr, "[time check: %d msec]\n", ms);
      if (ms > timeout && ms > extra_timeout)
	err("TO: Time limit exceeded");
    }
}

static void
sample_mem_peak(void)
{
  /*
   *  We want to find out the peak memory usage of the process, which is
   *  maintained by the kernel, but unforunately it gets lost when the
   *  process exits (it is not reported in struct rusage). Therefore we
   *  have to sample it whenever we suspect that the process is about
   *  to exit.
   */
  char buf[PROC_BUF_SIZE], *x;
  static int proc_status_fd;
  read_proc_file(buf, "status", &proc_status_fd);

  x = buf;
  while (*x)
    {
      char *key = x;
      while (*x && *x != ':' && *x != '\n')
	x++;
      if (!*x || *x == '\n')
	break;
      *x++ = 0;
      while (*x == ' ' || *x == '\t')
	x++;

      char *val = x;
      while (*x && *x != '\n')
	x++;
      if (!*x)
	break;
      *x++ = 0;

      if (!strcmp(key, "VmPeak"))
	{
	  int peak = atoi(val);
	  if (peak > mem_peak_kb)
	    mem_peak_kb = peak;
	}
    }

  if (verbose > 1)
    msg("[mem-peak: %u KB]\n", mem_peak_kb);
}

static void
boxkeeper(void)
{
  int syscall_count = (filter_syscalls ? 0 : 1);
  struct sigaction sa;

  is_ptraced = 1;

  bzero(&sa, sizeof(sa));
  sa.sa_handler = signal_int;
  sigaction(SIGINT, &sa, NULL);

  gettimeofday(&start_time, NULL);
  ticks_per_sec = sysconf(_SC_CLK_TCK);
  if (ticks_per_sec <= 0)
    die("Invalid ticks_per_sec!");

  if (timeout || wall_timeout)
    {
      sa.sa_handler = signal_alarm;
      sigaction(SIGALRM, &sa, NULL);
      alarm(1);
    }

  for(;;)
    {
      struct rusage rus;
      int stat;
      pid_t p;
      if (timer_tick)
	{
	  check_timeout();
	  timer_tick = 0;
	}
      p = wait4(box_pid, &stat, WUNTRACED, &rus);
      if (p < 0)
	{
	  if (errno == EINTR)
	    continue;
	  die("wait4: %m");
	}
      if (p != box_pid)
	die("wait4: unknown pid %d exited!", p);
      if (WIFEXITED(stat))
	{
	  box_pid = 0;
	  final_stats(&rus);
	  if (WEXITSTATUS(stat))
	    {
		  meta_printf("exitcode:%d\n", WEXITSTATUS(stat));
		  err("RE: Exited with error status %d", WEXITSTATUS(stat));
	    }
	  if (timeout && total_ms > timeout)
	    err("TO: Time limit exceeded");
	  if (wall_timeout && wall_ms > wall_timeout)
	    err("TO: Time limit exceeded (wall clock)");
	  flush_line();
	  fprintf(stderr, "OK (%d.%03d sec real, %d.%03d sec wall, %d MB, %d syscalls)\n",
	      total_ms/1000, total_ms%1000,
	      wall_ms/1000, wall_ms%1000,
	      (mem_peak_kb + 1023) / 1024,
	      syscall_count);
	  box_exit(0);
	}
      if (WIFSIGNALED(stat))
	{
	  box_pid = 0;
	  meta_printf("exitsig:%d\n", WTERMSIG(stat));
	  final_stats(&rus);
	  err("SG: Caught fatal signal %d%s", WTERMSIG(stat), (syscall_count ? "" : " during startup"));
	}
      if (WIFSTOPPED(stat))
	{
	  int sig = WSTOPSIG(stat);
	  if (sig == SIGTRAP)
	    {
	      if (verbose > 2)
		msg("[ptrace status %08x] ", stat);
	      static int stop_count;
	      if (!stop_count++)		/* Traceme request */
		msg(">> Traceme request caught\n");
	      else
		err("SG: Breakpoint");
	      ptrace(PTRACE_SYSCALL, box_pid, 0, 0);
	    }
	  else if (sig == (SIGTRAP | 0x80))
	    {
	      if (verbose > 2)
		msg("[ptrace status %08x] ", stat);
	      struct syscall_args a;
	      static unsigned int sys_tick, last_act;
	      static arg_t last_sys;
	      if (++sys_tick & 1)		/* Syscall entry */
		{
		  char namebuf[32];
		  int act;

		  get_syscall_args(&a, 0);
		  arg_t sys = a.sys;
		  msg(">> Syscall %-12s (%08jx,%08jx,%08jx) ", syscall_name(sys, namebuf), (intmax_t) a.arg1, (intmax_t) a.arg2, (intmax_t) a.arg3);
		  if (!exec_seen)
		    {
		      msg("[master] ");
		      if (sys == NATIVE_NR_execve)
			exec_seen = 1;
		    }
		  else if ((act = valid_syscall(&a)) >= 0)
		    {
		      last_act = act;
		      syscall_count++;
		      if (act & A_SAMPLE_MEM)
			sample_mem_peak();
		    }
		  else
		    {
		      /*
		       * Unfortunately, PTRACE_KILL kills _after_ the syscall completes,
		       * so we have to change it to something harmless (e.g., an undefined
		       * syscall) and make the program continue.
		       */
		      set_syscall_nr(&a, ~(arg_t)0);
		      err("FO: Forbidden syscall %s", syscall_name(sys, namebuf));
		    }
		  last_sys = sys;
		}
	      else					/* Syscall return */
		{
		  get_syscall_args(&a, 1);
		  if (a.sys == ~(arg_t)0)
		    {
		      /* Some syscalls (sigreturn et al.) do not return a value */
		      if (!(last_act & A_NO_RETVAL))
			err("XX: Syscall does not return, but it should");
		    }
		  else
		    {
		      if (a.sys != last_sys)
			err("XX: Mismatched syscall entry/exit");
		    }
		  if (last_act & A_NO_RETVAL)
		    msg("= ?\n");
		  else
		    msg("= %jd\n", (intmax_t) a.result);
		}
	      ptrace(PTRACE_SYSCALL, box_pid, 0, 0);
	    }
	  else if (sig == SIGSTOP)
	    {
	      msg(">> SIGSTOP\n");
	      if (ptrace(PTRACE_SETOPTIONS, box_pid, NULL, (void *) PTRACE_O_TRACESYSGOOD) < 0)
		die("ptrace(PTRACE_SETOPTIONS): %m");
	      ptrace(PTRACE_SYSCALL, box_pid, 0, 0);
	    }
	  else if (sig != SIGXCPU && sig != SIGXFSZ)
	    {
	      msg(">> Signal %d\n", sig);
	      sample_mem_peak();			/* Signal might be fatal, so update mem-peak */
	      ptrace(PTRACE_SYSCALL, box_pid, 0, sig);
	    }
	  else
	    {
	      meta_printf("exitsig:%d", sig);
	      err("SG: Received signal %d", sig);
	    }
	}
      else
	die("wait4: unknown status %x, giving up!", stat);
    }
}

static void
box_inside(int argc, char **argv)
{
  struct rlimit rl;
  char *args[argc+1];

  memcpy(args, argv, argc * sizeof(char *));
  args[argc] = NULL;
  if (set_cwd && chdir(set_cwd))
    die("chdir: %m");
  if (redir_stdin)
    {
      close(0);
      if (open(redir_stdin, O_RDONLY) != 0)
	die("open(\"%s\"): %m", redir_stdin);
    }
  if (redir_stdout)
    {
      close(1);
      if (open(redir_stdout, O_WRONLY | O_CREAT | O_TRUNC, 0666) != 1)
	die("open(\"%s\"): %m", redir_stdout);
    }
  if (redir_stderr)
    {
      close(2);
      if (open(redir_stderr, O_WRONLY | O_CREAT | O_TRUNC, 0666) != 2)
	die("open(\"%s\"): %m", redir_stderr);
    }
  else
    dup2(1, 2);
  setpgrp();

  if (memory_limit)
    {
      rl.rlim_cur = rl.rlim_max = memory_limit * 1024;
      if (setrlimit(RLIMIT_AS, &rl) < 0)
	die("setrlimit(RLIMIT_AS): %m");
    }

  rl.rlim_cur = rl.rlim_max = (stack_limit ? (rlim_t)stack_limit * 1024 : RLIM_INFINITY);
  if (setrlimit(RLIMIT_STACK, &rl) < 0)
    die("setrlimit(RLIMIT_STACK): %m");

  rl.rlim_cur = rl.rlim_max = 64;
  if (setrlimit(RLIMIT_NOFILE, &rl) < 0)
    die("setrlimit(RLIMIT_NOFILE): %m");

  char **env = setup_environment();
  if (filter_syscalls)
    {
      if (ptrace(PTRACE_TRACEME) < 0)
	die("ptrace(PTRACE_TRACEME): %m");
      /* Trick: Make sure that we are stopped until the boxkeeper wakes up. */
      raise(SIGSTOP);
    }
  execve(args[0], args, env);
  die("execve(\"%s\"): %m", args[0]);
}

static void
usage(void)
{
  fprintf(stderr, "Invalid arguments!\n");
  printf("\
Usage: box [<options>] -- <command> <arguments>\n\
\n\
Options:\n\
-a <level>\tSet file access level (0=none, 1=only defined with -p, 2=cwd, 3=/etc,/lib,...,\n\
\t\t4=whole fs, 9=no checks; needs -f)\n\
-c <dir>\tChange directory to <dir> first\n\
-e\t\tInherit full environment of the parent process\n\
-E <var>\tInherit the environment variable <var> from the parent process\n\
-E <var>=<val>\tSet the environment variable <var> to <val>; unset it if <var> is empty\n\
-f\t\tFilter system calls (-ff=very restricted)\n\
-F\t\tAllow fork and fork-related calls (children process _won't_ be traced)\n\
-i <file>\tRedirect stdin from <file>\n\
-k <size>\tLimit stack size to <size> KB (default: 0=unlimited)\n\
-m <size>\tLimit address space to <size> KB\n\
-M <file>\tOutput process information to <file> (name:value)\n\
-o <file>\tRedirect stdout to <file>\n\
-p <path>\tPermit access to the specified path (or subtree if it ends with a `/')\n\
-p <path>=<act>\tDefine action for the specified path (<act>=yes/no)\n\
-r <file>\tRedirect stderr to <file>\n\
-s <sys>\tPermit the specified syscall (be careful)\n\
-s <sys>=<act>\tDefine action for the specified syscall (<act>=yes/no/file)\n\
-t <time>\tSet run time limit (seconds, fractions allowed)\n\
-T\t\tAllow syscalls for measuring run time\n\
-v\t\tBe verbose (use multiple times for even more verbosity)\n\
-w <time>\tSet wall clock time limit (seconds, fractions allowed)\n\
-x <time>\tSet extra timeout, before which a timing-out program is not yet killed,\n\
\t\tso that its real execution time is reported (seconds, fractions allowed)\n\
");
  exit(2);
}

int
main(int argc, char **argv)
{
  int c;
  uid_t uid;

  while ((c = getopt(argc, argv, "a:c:eE:fFi:k:m:M:o:p:r:s:t:Tvw:x:")) >= 0)
    switch (c)
      {
      case 'a':
	file_access = atol(optarg);
	break;
      case 'c':
	set_cwd = optarg;
	break;
      case 'e':
	pass_environ = 1;
	break;
      case 'E':
	if (!set_env_action(optarg))
	  usage();
	break;
      case 'f':
	filter_syscalls++;
	break;
      case 'F':
	syscall_action[__NR_fork] = A_YES;
	syscall_action[__NR_vfork] = A_YES;
	syscall_action[__NR_clone] = A_YES;
	syscall_action[__NR_wait4] = A_YES;
	break;
      case 'k':
	stack_limit = atol(optarg);
	break;
      case 'i':
	redir_stdin = optarg;
	break;
      case 'm':
	memory_limit = atol(optarg);
	break;
      case 'M':
	meta_open(optarg);
	break;
      case 'o':
	redir_stdout = optarg;
	break;
      case 'p':
	if (!set_path_action(optarg))
	  usage();
	break;
      case 'r':
	redir_stderr = optarg;
	break;
      case 's':
	if (!set_syscall_action(optarg))
	  usage();
	break;
      case 't':
	timeout = 1000*atof(optarg);
	break;
      case 'T':
	syscall_action[__NR_times] = A_YES;
	break;
      case 'v':
	verbose++;
	break;
      case 'w':
        wall_timeout = 1000*atof(optarg);
	break;
      case 'x':
	extra_timeout = 1000*atof(optarg);
	break;
      default:
	usage();
      }
  if (optind >= argc)
    usage();

  sanity_check();
  uid = geteuid();
  if (setreuid(uid, uid) < 0)
    die("setreuid: %m");
  box_pid = fork();
  if (box_pid < 0)
    die("fork: %m");
  if (!box_pid)
    box_inside(argc-optind, argv+optind);
  else
    boxkeeper();
  die("Internal error: fell over edge of the world");
}
