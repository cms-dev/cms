use std::io;

fn main()
{
    let mut s = String::new();
    match io::stdin().read_line(&mut s)
    {
        Ok(_) => println!("correct {}", s.trim().parse::<i32>().unwrap()),
        Err(why) => panic!("{}", why),
    };
}
