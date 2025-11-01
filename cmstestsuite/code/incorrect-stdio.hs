main = getLine >>= putStrLn . ("incorrect " ++) . show . (read :: String -> Int)
