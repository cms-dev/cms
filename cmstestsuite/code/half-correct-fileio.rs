use std::fs::File;
use std::io::BufReader;
use std::io::prelude::*;

fn main()
{
    let mut input = BufReader::new(File::open("input.txt").unwrap());
    let mut output = File::create("output.txt").unwrap();
    let mut s = String::new();
    match input.read_line(&mut s)
    {
        Ok(_) =>
        {
            let n = s.trim().parse::<i32>().unwrap();
            let _ = write!(output, "correct {}", if n % 2 == 0 {n} else {0});
        },
        Err(why) => panic!("{}", why),
    };
}
