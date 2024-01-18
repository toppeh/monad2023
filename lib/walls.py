def getWalls( square ):
    WALLS = [0b1000, 0b0100, 0b0010, 0b0001] # north, east, south, west
    return {
        "north": square & WALLS[0] != 0,
        "east": square & WALLS[1] != 0,
        "south": square & WALLS[2] != 0,
        "west": square & WALLS[3] != 0
    }