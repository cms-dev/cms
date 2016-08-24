main = do
    n <- (read :: String -> Int) `fmap` getLine
    putStrLn $ "correct " ++ show n
    last [0 ..] `seq` return ()
