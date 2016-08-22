main = do
    n <- (read :: String -> Int) `fmap` readFile "input.txt"
    writeFile "output.txt" $ "correct " ++ show (if odd n then n else 0) ++ "\n"
