use std::io;

fn main()
{
    let mut s = String::new();
    match io::stdin().read_line(&mut s)
    {
        Ok(_) =>
        {
			let n = s.trim().parse::<i32>().unwrap();
			println!("correct {}", if n % 2 == 0 {n} else {0});
		},
        Err(why) => panic!("{}", why),
    };
}
