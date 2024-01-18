from math import sqrt

# Returns a list of neighbours for a given cell.
# A neighbour is represented as a tuple of (x, y, distance_to_target, rotation, previous_cell)
def getNeighbours(position, target, walls):
    neighbours = dict()
    x = position['x']
    y = position['y']
    if not walls['north']:
        neighbours[(x, y-1)] = 0
        
    if not walls['east']:
        neighbours[(x+1, y)] = 90
        
    if not walls['south']:
        neighbours[(x, y+1)] = 180
        
    if not walls['west']:
        neighbours[(x-1, y)] = 270
        
    # if not walls['north'] and not walls['east']:
    #     neighbours.append(((x+1, y-1), calculateDistance((x+1, y-1), target), 45))
    # if not walls['east'] and not walls['south']:
    #     neighbours.append(((x+1, y+1), calculateDistance((x+1, y+1), target), 135))
    # if not walls['south'] and not walls['west']:
    #     neighbours.append(((x-1, y+1), calculateDistance((x-1, y+1), target), 225))
    # if not walls['west'] and not walls['north']:
    #     neighbours.append(((x-1, y-1), calculateDistance((x-1, y-1), target), 315))
    return neighbours

def calculateDistance(position, target):
    return sqrt((position[0] - target['x'])**2 + (position[1] - target['y'])**2)

# Sets the neighbour with the same rotation as the last neighbour in the list.
def sortByRotation(neighbours, rotation):
    for i in range(len(neighbours)):
        if neighbours[i][2] == rotation:
            neighbour = neighbours.pop(i)
            neighbours.append(neighbour)
            break
    return neighbours