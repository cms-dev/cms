main = getLine >>= putStrLn . ("correct " ++) . show . (read :: String -> Int)
