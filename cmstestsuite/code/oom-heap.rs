use std::io;
use std::cmp::max;

fn main()
{
    let n = 128 * 1024 * 1024;
    let mut s = String::new();
    let g: usize = match io::stdin().read_line(&mut s)
    {
        Ok(_) => s.trim().parse().unwrap(),
        Err(why) => panic!("{}", why),
    };
    let v: Vec<_> = (0..max(n, g + 1)).collect();
    println!("correct {}", v[g]);
}
