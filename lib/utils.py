from math import sqrt

# Returns a list of neighbours for a given cell.
# A neighbour is represented as a tuple of (x, y, distance_to_target, rotation, previous_cell)
def getNeighbours(position, target, walls):
    neighbours = dict()
    x = position[0]
    y = position[1]
    if not walls['north']:
        neighbours[(x, y-1)] = 0
    if not walls['east']:
        neighbours[(x+1, y)] = 90
    if not walls['south']:
        neighbours[(x, y+1)] = 180
    if not walls['west']:
        neighbours[(x-1, y)] = 270        
    return neighbours

# Heuristic function for A* algorithm. Adjust factor to change priorization.
# Smaller factor -> more time, better score.
def calculateDistance(position, target):
    factor = 1000
    return factor * sqrt((position[0] - target['x'])**2 + (position[1] - target['y'])**2)


# Get walls for a cell.
def getWalls( square ):
    WALLS = [0b1000, 0b0100, 0b0010, 0b0001] # north, east, south, west
    return {
        "north": square & WALLS[0] != 0,
        "east": square & WALLS[1] != 0,
        "south": square & WALLS[2] != 0,
        "west": square & WALLS[3] != 0
    }


# Calculate counter-rotation.
def get_opposite_angle(angle):
    opposite_angle = angle + 180
    if opposite_angle >= 360:
        opposite_angle -= 360
    return opposite_angle

# Calculates the rotation for two dialonally adjacent cells. This probably could be calculated fancily but this works.
def calculate_rotation_from_position(origin_position, target_position):
    x_diff = target_position[0] - origin_position[0]
    y_diff = target_position[1] - origin_position[1]
    if x_diff == 1 and y_diff == -1:
        return 45
    elif x_diff == 1 and y_diff == 1:
        return 135
    elif x_diff == -1 and y_diff == 1:
        return 225
    elif x_diff == -1 and y_diff == -1:
        return 315
    else:
        # Input cell are not diagonally adjacent.
        print("Error: calculate_rotation_from_position() got invalid arguments.")
        return None

# Forms a path from the target cell to the origin cell.
def form_path(target, cells, start):
    path = list()
    while cells[target].previous_cell is not None:
        path.insert(0, target)
        target = cells[target].previous_cell
    # Insert root cell.
    path.insert(0, target)
    print("Formed path:", path)
    return path

# Will optimize (=diagonalize) path beginning from the start.
def optimize_path(path, cells):
    optimized_path = list()
    i = 0
    while i < len(path):
        current_cell = path[i]
        if i == len(path) - 1:
            # Target cell.
            optimized_path.append(path[i])
            break
        
        next_cell = path[i+1]
        if i + 1 == len(path) - 1:
            # Final two cells in path, can't cut corners.
            optimized_path.append(path[i])
            optimized_path.append(path[i+1])
            i += 2  # Will end loop.
            break
        
        next_next_cell = path[i+2]
        # Check if corner can be cut.
        if abs(current_cell[0] - next_next_cell[0]) < 2 and abs(current_cell[1] - next_next_cell[1]) < 2:
            # Corner can be cutted.
            optimized_path.append(current_cell)
            i += 2
        else:
            optimized_path.append(current_cell)
            i += 1
    return optimized_path