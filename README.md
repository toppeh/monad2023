# monad2023
This repo is a solution to Monad's 2023 recruiting code challenge.

The problem was to guide a miner to a lump of gold in a mine.
My solution was to use two graph algorithms, DFS and A*, to find a way through
the mine. 

level 1: A*, dist_to_go_factor: 1, Score 12, Timer: 578
level 2: DFS w/heuristics, Score: 124, Timer: 597
level 3: A*, dist_to_go_factor: 1.5, Score 54, Timer 29478 
level 4: DFS w/heuristics, Score: 222, Timer: 28682s
level 5: DFS no heuristics, Score: 268, Timer 29311
level 6: DFS w/heuristics, Score: 815, Timer: 31715 (lähti aikamoiselle kiertoajelulle aluksi)
level 7: DFS w/heuristics&loop detection, Score: 4008, Timer: 157707

Overall DFS was the better choice even though shortest path was desired. Problem with A*
was with this challenge's twist: maze had to be walked through with no 'teleporting' as is usual
with graph algorithms. Say you are on node (3, 4) and the next node pulled from prio queue is (10, 3).
To continue with A* you first would need to make your way to (10, 3). This takes way too much
time when the maze gets bigger. DFS on the other hand behaves desirably even though it won't necessarily find the shortest route.