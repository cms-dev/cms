use std::fs::File;
use std::io::BufReader;
use std::io::prelude::*;

fn main()
{
    let mut input = BufReader::new(File::open("input.txt").unwrap());
    let mut output = File::create("output.txt").unwrap();
    let mut s = String::new();
    let _ = match input.read_line(&mut s)
    {
        Ok(_) => write!(output, "incorrect {}", s.trim().parse::<i32>().unwrap()),
        Err(why) => panic!("{}", why),
    };
}
