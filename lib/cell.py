class Cell:
    def __init__(self, x, y, estimate=0):
        self.x = x
        self.y = y
        self.neighbours = dict()
        self.previous_cell = None
        self.estimate = estimate
        self.visited = False

    def set_neighbours(self, neighbours):
        self.neighbours.update(neighbours)
        # print("neighbours:", neighbours)
        # print("self.neighbours:", self.neighbours)
    
    def set_previous_cell(self, position):
        self.previous_cell = position

    def set_visited(self):
        self.visited = True