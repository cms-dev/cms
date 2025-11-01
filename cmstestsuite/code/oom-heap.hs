import Data.Array.IArray

main = do
    n <- read `fmap` getLine
    let a = array (0, 128 * 1024 * 1024) [(10000, n)] :: Array Int Int
    putStrLn $ "correct " ++ (show $ a ! 10000)
