import Data.Array.IArray

main = do
    n <- read `fmap` getLine
    let a = array (0, 125 * 1000 * 1000) [(10000, n)] :: Array Int Int
    putStrLn $ "correct " ++ (show $ a ! 10000)
