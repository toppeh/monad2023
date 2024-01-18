class Cell:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.neighbours = dict()
        self.previous_cell = None

    def set_neighbours(self, neighbours):
        self.neighbours = neighbours
        # print("neighbours:", neighbours)
        # print("self.neighbours:", self.neighbours)
    
    def set_previous_cell(self, position):
        self.previous_cell = position