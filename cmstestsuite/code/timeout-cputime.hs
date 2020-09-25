import Control.Monad

main :: IO ()
main = do
    n <- (read :: String -> Int) `fmap` getLine
    putStrLn $ "correct " ++ show n
    forever $ return ()
