import System.Exit

main = getLine >>= putStrLn . ("correct " ++) . show . (read :: String -> Int) >> exitFailure
