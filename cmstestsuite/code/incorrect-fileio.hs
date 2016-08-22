main = readFile "input.txt" >>= writeFile "output.txt" . (++ "\n") . ("incorrect " ++) . show . (read :: String -> Int)
