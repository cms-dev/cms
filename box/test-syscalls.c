int main(void)
{
  /*
   *  This program calls exit(42) using several different
   *  syscall mechanisms.
   */
#if defined(TEST_INT80)
  asm volatile("int $0x80" : : "a" (1), "b" (42) : "memory");
#elif defined(TEST_SYSCALL_32)
  asm volatile("syscall" : : "a" (1), "b" (42) : "memory");
#elif defined(TEST_SYSCALL_64)
  asm volatile("syscall" : : "a" (60), "D" (42) : "memory");
#elif defined(TEST_SYSENTER_32)
  /*
   *  Hack alert! The SYSENTER instruction does not record
   *  the return address, so the syscall returns to a fixed
   *  address inside the VDSO. However, we need not worry
   *  about all this, since exit() never returns anyway.
   */
  asm volatile("sysenter" : : "a" (1), "b" (42) : "memory");
#else
#error "TEST_xxx must be defined."
#endif
  return 1;
}
