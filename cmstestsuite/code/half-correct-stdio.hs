main = do
    n <- (read :: String -> Int) `fmap` getLine
    putStrLn $ "correct " ++ show (if odd n then n else 0)
