from enum import Enum
import random
from statistics import mean, median
import numpy as np


class Line(Enum):
    ATT = 'ATT'
    MATT = 'MATT'
    DEX = 'DEX'
    INT = 'INT'
    
class Item:
    line1: Line = None
    line2: Line = None
    line3: Line = None
    
    def __init__(self, stamped: bool):
        self.line1 = random.choice(list(Line))
        self.line2 = random.choice(list(Line))
        
        if stamped:
            self.line3 = random.choice(list(Line))

def roll_item(item: Item):
    item.line1 = random.choice(list(Line))
    item.line2 = random.choice(list(Line))
    
    if item.line3 is not None:
        item.line3 = random.choice(list(Line))

def stamp_item(item: Item):
    if item.line3 is None:
        item.line3 = random.choice(list(Line))
    else:
        raise Exception('Item already stamped')

def roll_until_3_line(item: Item) -> int:
    # Assumes item is already stamped, roll until 3L att
    # Returns the # of cubes used
    trials = 0
    while not (item.line1 == Line.ATT and item.line2 == Line.ATT and item.line3 == Line.ATT):
        item.line1 = random.choice(list(Line))
        item.line2 = random.choice(list(Line))
        item.line3 = random.choice(list(Line))
        trials += 1
    
    #print(f"Hit 3L after {trials} trials")
    return trials

def roll_until_2_line_then_stamp(item: Item) -> int:
    # Assumes the item is not stamped, roll until 2L att, then stamp
    trials = 0
    while not (item.line1 == Line.ATT and item.line2 == Line.ATT):
        item.line1 = random.choice(list(Line))
        item.line2 = random.choice(list(Line))
        trials += 1
    
    #print(f"Hit 2L after {trials} trials. Stamping")
    item.line3 = random.choice(list(Line))
    if (item.line1 == Line.ATT and item.line2 == Line.ATT and item.line3 == Line.ATT):
        pass
    else:
        extra_trials = roll_until_3_line(item)
        trials += extra_trials
        #print(f"Did not hit 3L after stamping. Total number of cubes: {trials}")
    
    return trials


def main():
    num_trials = 100000
    
    number_rolls_3l = []
    number_rolls_2l_then_stamp = []
    
    for i in range(num_trials):
        if i % 100 == 0:
            print(f"trial {i}")
        reg_item = Item(stamped=True)
        unstamped = Item(stamped=False)
        number_rolls_3l.append(roll_until_3_line(reg_item))
        number_rolls_2l_then_stamp.append(roll_until_2_line_then_stamp(unstamped))
        
    np_3l = np.array(number_rolls_3l)
    np_2l_stamp = np.array(number_rolls_2l_then_stamp)
    
    print(f"Performed {num_trials} trials.")
    print(f"========Directly rolling for 3L========")
    print(f"Average # of Cubes: {np.mean(np_3l)}")
    print(f"Median # of Cubes: {np.median(np_3l)}")
    print(f"Mininum number of cubes: {min(np_3l)}")
    print(f"5th Percentile: {np.percentile(np_3l, 5)}")
    print(f"20th Percentile: {np.percentile(np_3l, 20)}")
    print(f"70th Percentile: {np.percentile(np_3l, 70)}")
    print(f"90th Percentile: {np.percentile(np_3l, 90)}")
    print(f"99th Percentile: {np.percentile(np_3l, 99)}")
    print(f"Maximum number of cubes: {max(np_3l)}")
    print(f"========Rolling for 2L then stamp, then rolling for 3L========")
    print(f"Average # of Cubes: {np.mean(np_2l_stamp)}")
    print(f"Median # of Cubes: {np.median(np_2l_stamp)}")
    print(f"Mininum number of cubes: {min(np_2l_stamp)}")
    print(f"5th Percentile: {np.percentile(np_2l_stamp, 5)}")
    print(f"20th Percentile: {np.percentile(np_2l_stamp, 20)}")
    print(f"70th Percentile: {np.percentile(np_2l_stamp, 70)}")
    print(f"90th Percentile: {np.percentile(np_2l_stamp, 90)}")
    print(f"99th Percentile: {np.percentile(np_2l_stamp, 99)}")
    print(f"Maximum number of cubes: {max(np_2l_stamp)}")
    
if __name__ == '__main__':
    main()