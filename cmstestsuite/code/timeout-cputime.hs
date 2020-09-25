loop :: Int -> Int
loop x = loop x

main :: IO ()
main = do
    n <- (read :: String -> Int) `fmap` getLine
    putStrLn $ "correct " ++ show n
    loop 1 `seq` return ()
