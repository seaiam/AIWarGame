from __future__ import annotations
import argparse
import copy
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import math
from time import sleep
from typing import Tuple, TypeVar, Type, Iterable, ClassVar
import random
import time
import requests
import logging

# maximum and minimum values for our heuristic scores (usually represents an end of game condition)
MAX_HEURISTIC_SCORE = 2000000000
MIN_HEURISTIC_SCORE = -2000000000
logger = logging.getLogger("")

class UnitType(Enum):
    """Every unit type."""
    AI = 0
    Tech = 1
    Virus = 2
    Program = 3
    Firewall = 4

class Player(Enum):
    """The 2 players."""
    Attacker = 0
    Defender = 1

    def next(self) -> Player:
        """The next (other) player."""
        if self is Player.Attacker:
            return Player.Defender
        else:
            return Player.Attacker

class GameType(Enum):
    AttackerVsDefender = 0
    AttackerVsComp = 1
    CompVsDefender = 2
    CompVsComp = 3

##############################################################################################################

@dataclass(slots=True)
class Unit:
    player: Player = Player.Attacker
    type: UnitType = UnitType.Program
    health : int = 9
    # class variable: damage table for units (based on the unit type constants in order)
    damage_table : ClassVar[list[list[int]]] = [
        [3,3,3,3,1], # AI
        [1,1,6,1,1], # Tech
        [9,6,1,6,1], # Virus
        [3,3,3,3,1], # Program
        [1,1,1,1,1], # Firewall
    ]
    # class variable: repair table for units (based on the unit type constants in order)
    repair_table : ClassVar[list[list[int]]] = [
        [0,1,1,0,0], # AI
        [3,0,0,3,3], # Tech
        [0,0,0,0,0], # Virus
        [0,0,0,0,0], # Program
        [0,0,0,0,0], # Firewall
    ]

    def is_alive(self) -> bool:
        """Are we alive ?"""
        return self.health > 0

    def mod_health(self, health_delta : int):
        """Modify this unit's health by delta amount."""
        self.health += health_delta
        if self.health < 0:
            self.health = 0
        elif self.health > 9:
            self.health = 9

    def to_string(self) -> str:
        """Text representation of this unit."""
        p = self.player.name.lower()[0]
        t = self.type.name.upper()[0]
        return f"{p}{t}{self.health}"
    
    def __str__(self) -> str:
        """Text representation of this unit."""
        return self.to_string()
    
    def damage_amount(self, target: Unit) -> int:
        """How much can this unit damage another unit."""
        amount = self.damage_table[self.type.value][target.type.value]
        if target.health - amount < 0:
            return target.health
        return amount

    def repair_amount(self, target: Unit) -> int:
        """How much can this unit repair another unit."""
        amount = self.repair_table[self.type.value][target.type.value]
        if target.health + amount > 9:
            return 9 - target.health
        return amount

##############################################################################################################

@dataclass(slots=True)
class Coord:
    """Representation of a game cell coordinate (row, col)."""
    row : int = 0
    col : int = 0

    def __hash__(self):
        return hash((self.row, self.col))


    def col_string(self) -> str:
        """Text representation of this Coord's column."""
        coord_char = '?'
        if self.col < 16:
                coord_char = "0123456789abcdef"[self.col]
        return str(coord_char)

    def row_string(self) -> str:
        """Text representation of this Coord's row."""
        coord_char = '?'
        if self.row < 26:
                coord_char = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[self.row]
        return str(coord_char)

    def to_string(self) -> str:
        """Text representation of this Coord."""
        return self.row_string()+self.col_string()
    
    def __str__(self) -> str:
        """Text representation of this Coord."""
        return self.to_string()
    
    def clone(self) -> Coord:
        """Clone a Coord."""
        return copy.copy(self)

    def iter_range(self, dist: int) -> Iterable[Coord]:
        """Iterates over Coords inside a rectangle centered on our Coord."""
        for row in range(self.row-dist,self.row+1+dist):
            for col in range(self.col-dist,self.col+1+dist):
                yield Coord(row,col)

    def iter_adjacent(self) -> Iterable[Coord]:
        """Iterates over adjacent Coords."""
        yield Coord(self.row-1,self.col)
        yield Coord(self.row,self.col-1)
        yield Coord(self.row+1,self.col)
        yield Coord(self.row,self.col+1)

    def iter_surrounding(self) -> Iterable[Coord]:
        """Iterates over adjacent Coords."""
        yield Coord(self.row-1,self.col)
        yield Coord(self.row,self.col-1)
        yield Coord(self.row+1,self.col)
        yield Coord(self.row+1,self.col+1)
        yield Coord(self.row,self.col+1)
        yield Coord(self.row+1,self.col-1)
        yield Coord(self.row-1,self.col+1)
        yield Coord(self.row-1,self.col-1)
    
    def manhattan_distance(self, other):
        return abs(self.row - other.row) + abs(self.col - other.col)
    
    @classmethod
    def from_string(cls, s : str) -> Coord | None:
        """Create a Coord from a string. ex: D2."""
        s = s.strip()
        for sep in " ,.:;-_":
                s = s.replace(sep, "")
        if (len(s) == 2):
            coord = Coord()
            coord.row = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".find(s[0:1].upper())
            coord.col = "0123456789abcdef".find(s[1:2].lower())
            return coord
        else:
            return None

##############################################################################################################

@dataclass(slots=True)
class CoordPair:
    """Representation of a game move or a rectangular area via 2 Coords."""
    src : Coord = field(default_factory=Coord)
    dst : Coord = field(default_factory=Coord)

    def to_string(self) -> str:
        """Text representation of a CoordPair."""
        return self.src.to_string()+" "+self.dst.to_string()
    
    def __str__(self) -> str:
        """Text representation of a CoordPair."""
        return self.to_string()

    def clone(self) -> CoordPair:
        """Clones a CoordPair."""
        return copy.copy(self)

    def iter_rectangle(self) -> Iterable[Coord]:
        """Iterates over cells of a rectangular area."""
        for row in range(self.src.row,self.dst.row+1):
            for col in range(self.src.col,self.dst.col+1):
                yield Coord(row,col)

    @classmethod
    def from_quad(cls, row0: int, col0: int, row1: int, col1: int) -> CoordPair:
        """Create a CoordPair from 4 integers."""
        return CoordPair(Coord(row0,col0),Coord(row1,col1))
    
    @classmethod
    def from_dim(cls, dim: int) -> CoordPair:
        """Create a CoordPair based on a dim-sized rectangle."""
        return CoordPair(Coord(0,0),Coord(dim-1,dim-1))
    
    @classmethod
    def from_string(cls, s : str) -> CoordPair | None:
        """Create a CoordPair from a string. ex: A3 B2"""
        s = s.strip()
        for sep in " ,.:;-_":
                s = s.replace(sep, "")
        if (len(s) == 4):
            coords = CoordPair()
            coords.src.row = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".find(s[0:1].upper())
            coords.src.col = "0123456789abcdef".find(s[1:2].lower())
            coords.dst.row = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".find(s[2:3].upper())
            coords.dst.col = "0123456789abcdef".find(s[3:4].lower())
            return coords
        else:
            return None

##############################################################################################################

@dataclass(slots=True)
class Options:
    """Representation of the game options."""
    dim: int = 5
    max_depth : int | None = 4
    min_depth : int | None = 2
    max_time : float | None = 5.0
    game_type : GameType = GameType.AttackerVsDefender
    alpha_beta : bool = True
    max_turns : int | None = 100
    heuristic : int | None = 0
    randomize_moves : bool = True
    broker : str | None = None

##############################################################################################################

@dataclass(slots=True)
class Stats:
    """Representation of the global game statistics."""
    evaluations_per_depth : dict[int,int] = field(default_factory=dict)
    total_seconds: float = 0.0

##############################################################################################################

@dataclass(slots=True)
class Game:


    """Representation of the game state."""
    board: list[list[Unit | None]] = field(default_factory=list)
    curr_player: Player = Player.Attacker
    turns_played : int = 0
    options: Options = field(default_factory=Options)
    stats: Stats = field(default_factory=Stats)
    _attacker_has_ai : bool = True
    _defender_has_ai : bool = True
    unit_position: list[Coord] = field(default_factory=list)
    listOfCandidateMove: list[int] = field(default_factory=list)
    count: int = 0
    start_time: datetime = None
    def __post_init__(self):
        """Automatically called after class init to set up the default board state."""
        dim = self.options.dim
        self.board = [[None for _ in range(dim)] for _ in range(dim)]
        md = dim-1
        self.set(Coord(0,0),Unit(player=Player.Defender,type=UnitType.AI))
        self.set(Coord(1,0),Unit(player=Player.Defender,type=UnitType.Tech))
        self.set(Coord(0,1),Unit(player=Player.Defender,type=UnitType.Tech))
        self.set(Coord(2,0),Unit(player=Player.Defender,type=UnitType.Firewall))
        self.set(Coord(0,2),Unit(player=Player.Defender,type=UnitType.Firewall))
        self.set(Coord(1,1),Unit(player=Player.Defender,type=UnitType.Program))
        self.set(Coord(md,md),Unit(player=Player.Attacker,type=UnitType.AI))
        self.set(Coord(md-1,md),Unit(player=Player.Attacker,type=UnitType.Virus))
        self.set(Coord(md,md-1),Unit(player=Player.Attacker,type=UnitType.Virus))
        self.set(Coord(md-2,md),Unit(player=Player.Attacker,type=UnitType.Program))
        self.set(Coord(md,md-2),Unit(player=Player.Attacker,type=UnitType.Program))
        self.set(Coord(md-1,md-1),Unit(player=Player.Attacker,type=UnitType.Firewall))

        self.unit_position = [
            Coord(0, 0), #Defender AI
            Coord(1, 0), #Defender Tech
            Coord(0, 1), #Defender Tech
            Coord(2, 0), #Defender Firewall
            Coord(0, 2), #Defender Firewall
            Coord(1, 1), #Defender Program
            Coord(md, md), #Attacker AI
            Coord(md-1, md), #Attacker Virus
            Coord(md, md-1), #Attacker Virus
            Coord(md-2, md), #Attacker Program
            Coord(md, md-2), #Attacker Program
            Coord(md-1, md-1) #Attacker FireWall
       ]
        self.start_time = datetime.now()

    def clone(self) -> Game: 
        """Make a new copy of a game for minimax recursion.
        Shallow copy of everything except the board (options and stats are shared).
        """
        new = copy.copy(self)
        new.board = copy.deepcopy(self.board)
        new.unit_position = copy.deepcopy(self.unit_position)
        return new

    def is_empty(self, coord : Coord) -> bool:
        """Check if contents of a board cell of the game at Coord is empty (must be valid coord)."""
        return self.board[coord.row][coord.col] is None

    def get(self, coord : Coord) -> Unit | None:
        """Get contents of a board cell of the game at Coord."""
        if self.is_valid_coord(coord):
            return self.board[coord.row][coord.col]
        else:
            return None

    def set(self, coord : Coord, unit : Unit | None):
        """Set contents of a board cell of the game at Coord."""
        if self.is_valid_coord(coord):
            self.board[coord.row][coord.col] = unit
    
    def set_position(self, coord : Coord, index: int):
        """Set contents of our position array  to Coord"""
        self.unit_position[index] = coord

    def remove_dead(self, coord: Coord):
        """Remove unit at Coord if dead."""
        unit = self.get(coord)
        if unit is not None and not unit.is_alive():
            for i, pos in enumerate(self.unit_position):
                if pos == coord:
                    self.set_position(None,i)
            self.set(coord,None)
            if unit.type == UnitType.AI:
                if unit.player == Player.Attacker:
                    self._attacker_has_ai = False
                else:
                    self._defender_has_ai = False

    def mod_health(self, coord : Coord, health_delta : int):
        """Modify health of unit at Coord (positive or negative delta)."""
        target = self.get(coord)
        if target is not None:
            target.mod_health(health_delta)
            self.remove_dead(coord)

    def possible_move(self, coord : Coord) -> Iterable[Coord]:
        unit = self.get(coord)
        for dest in coord.iter_adjacent():
            move = CoordPair(coord, dest)
            if(self.is_valid_move(move) and self.is_permissible_move(move)):
                yield dest

    def is_valid_move(self, coords : CoordPair) -> bool:
        """Validate a move expressed as a CoordPair. TODO: WRITE MISSING CODE!!!"""
        if not self.is_valid_coord(coords.src) or not self.is_valid_coord(coords.dst):
            # print("invalid coords")
            return False
        unit = self.get(coords.src)
        if unit is None or unit.player != self.curr_player:
            # print("unit is not yours to play ")
            return False
        # if i cant repair friendly unit
        if self.get(coords.dst) is not None and unit.repair_amount(self.get(coords.dst))== 0 and self.get(coords.dst)!= unit and self.get(coords.dst).player == unit.player:
            # print("if i cant repair friendly unit")
            return False
        # if friendly unit has 9 health
        if self.get(coords.dst) is not None and self.get(coords.dst)!= unit and self.get(coords.dst).player == self.curr_player and self.get(coords.dst).health == 9:
            # print("if friendly unit has 9 health")
            return False
        if abs(coords.src.row-coords.dst.row)> 1 or abs(coords.src.col-coords.dst.col)> 1 :
            # print("move too big more than one unit ")
            return False
        if self.is_engaged(coords.src) and (unit.type==UnitType.AI or unit.type==UnitType.Firewall or unit.type==UnitType.Program) and self.get(coords.dst) is None:
            # print("engaged and dest is none")
            return False
        # print("valid move")
        return True

    def is_permissible_move(self, coords : CoordPair) -> bool:
        """To verify that attackers and defenders are doing permissible move"""
        unit = self.get(coords.src)
        if self.get(coords.dst) is not None:
            # print("move permissible") 
            return True
        if unit.player == Player.Attacker:
            # down or right  return false 
            if (unit.type==UnitType.AI or unit.type==UnitType.Firewall or unit.type==UnitType.Program):
                if (coords.src.row-coords.dst.row)<0  or (coords.src.col-coords.dst.col)<0 :
                    # print("move not permissible")
                    return False
                else:
                    # print("move permissible")                    
                    return True
            else: 
                # print("move permissible")                
                return True
        else: 
            # up or left return false
            if (unit.type==UnitType.AI or unit.type==UnitType.Firewall or unit.type==UnitType.Program):
                if (coords.src.row-coords.dst.row)>0  or (coords.src.col-coords.dst.col)>0 :
                    # print("move not permissible")                    
                    return False
                else:
                    # print("move permissible")                     
                    return True
            else: 
                # print("move permissible") 
                return True             
                
    def is_engaged(self, coord: Coord) -> bool:
        """Check if there is opponent in the adjacent coordinates to the given coordinate."""
        for adjacent_coord in coord.iter_adjacent():
            if self.is_valid_coord(adjacent_coord) and not self.is_empty(adjacent_coord) and self.get(adjacent_coord).player!= self.curr_player:
                # print("unit is engaged")               
                return True
        # print("unit is NOT engaged")
        return False        

    def is_engaged_minimax(self, coord: Coord) -> bool:
        """Check if there is opponent in the adjacent coordinates to the given coordinate."""
        for adjacent_coord in coord.iter_adjacent():
            if self.is_valid_coord(adjacent_coord) and not self.is_empty(adjacent_coord) and self.get(adjacent_coord).player!= self.curr_player:
                return True
        return False     

    def is_valid_move_minimax(self, coords : CoordPair) -> bool:
        """Validate a move expressed as a CoordPair. TODO: WRITE MISSING CODE!!!"""
        if not self.is_valid_coord(coords.src) or not self.is_valid_coord(coords.dst):
            return False
        unit = self.get(coords.src)
        if unit is None or unit.player != self.curr_player:
            return False
        # if i cant repair friendly unit
        if self.get(coords.dst) is not None and unit.repair_amount(self.get(coords.dst))== 0 and self.get(coords.dst)!= unit and self.get(coords.dst).player == unit.player:
            return False
        # if friendly unit has 9 health
        if self.get(coords.dst) is not None and self.get(coords.dst)!= unit and self.get(coords.dst).player == self.curr_player and self.get(coords.dst).health == 9:
            return False
        if abs(coords.src.row-coords.dst.row)> 1 or abs(coords.src.col-coords.dst.col)> 1 :
            return False
        if self.is_engaged(coords.src) and (unit.type==UnitType.AI or unit.type==UnitType.Firewall or unit.type==UnitType.Program) and self.get(coords.dst) is None:
            return False
        return True

    def is_permissible_move_minimax(self, coords : CoordPair) -> bool:
        """To verify that attackers and defenders are doing permissible move"""
        unit = self.get(coords.src)
        if self.get(coords.dst) is not None:
            return True
        if unit.player == Player.Attacker:
            # down or right  return false 
            if (unit.type==UnitType.AI or unit.type==UnitType.Firewall or unit.type==UnitType.Program):
                if (coords.src.row-coords.dst.row)<0  or (coords.src.col-coords.dst.col)<0 :
                    return False
                else:                   
                    return True
            else:                
                return True
        else: 
            # up or left return false
            if (unit.type==UnitType.AI or unit.type==UnitType.Firewall or unit.type==UnitType.Program):
                if (coords.src.row-coords.dst.row)>0  or (coords.src.col-coords.dst.col)>0 :                  
                    return False
                else:                     
                    return True
            else: 
                return True                 
    
    #destUnit gets attacked by current unit
    def attack_unit(self, destUnit: Unit, currentUnit: Unit, coords : CoordPair):
        damageToDest = currentUnit.damage_amount(destUnit)
        damageToUnit = destUnit.damage_amount(currentUnit)
        self.mod_health(coords.dst,-damageToDest)
        self.mod_health(coords.src,-damageToUnit)
        logger.info(f"""{currentUnit.player.name} attacks {destUnit.player.name} and inflicts {damageToDest} damage.
        {destUnit.player.name} inflicts {damageToUnit} damage to {currentUnit.player.name}.""")
    #mini max call with no print()
    def attack_unit_mini_max(self, destUnit: Unit, currentUnit: Unit, coords : CoordPair):
        damageToDest = currentUnit.damage_amount(destUnit)
        damageToUnit = destUnit.damage_amount(currentUnit)
        self.mod_health(coords.dst,-damageToDest)
        self.mod_health(coords.src,-damageToUnit)
    #self destruct
    def self_destruct(self, currentUnit: Unit, coords : CoordPair):
        logger.info(f"{currentUnit.player.name} self destructs")
        print(f"{currentUnit.player.name} self destructs")
        self.mod_health(coords.src,-currentUnit.health)
        for surounding in coords.src.iter_surrounding():
            collateral = self.get(surounding)
            if self.is_valid_coord(surounding) and collateral is not None:
                print(f"{collateral.player.name}'s {collateral.type.name} at {surounding} receives 2 damage")
                logger.info(f"{collateral.player.name}'s {collateral.type.name} at {surounding} receives 2 damage")
                self.mod_health(surounding,-2)
    # mini max call with no print()
    def self_destruct_mini_max(self, currentUnit: Unit, coords : CoordPair):
        self.mod_health(coords.src,-currentUnit.health)
        for surounding in coords.src.iter_surrounding():
            collateral = self.get(surounding)
            if self.is_valid_coord(surounding) and collateral is not None:
                self.mod_health(surounding,-2)
    # currentUnit repairs destUnit
    def repair_unit(self,destUnit: Unit, currentUnit: Unit, coords : CoordPair ):
        repair = currentUnit.repair_amount(destUnit)
        # if repair == 0 or destUnit.health == 9:
        #     print(f"{currentUnit.type.name} can't repair {destUnit.type.name}")
        #     return False
        logger.info(f"{currentUnit.type.name} repairs {destUnit.type.name} by {repair}")
        print(f"{currentUnit.type.name} repairs {destUnit.type.name} by {repair}")
        self.mod_health(coords.dst,repair)
    # mini max call with no print()
    def repair_unit_mini_max(self,destUnit: Unit, currentUnit: Unit, coords : CoordPair ):
        repair = currentUnit.repair_amount(destUnit)
        if repair == 0 or destUnit.health == 9:
            return False
        self.mod_health(coords.dst,repair)
    
    def perform_move(self, coords : CoordPair) -> Tuple[bool,str]:
        """Validate and perform a move expressed as a CoordPair. TODO: WRITE MISSING CODE!!!"""
        if self.is_valid_move(coords) and self.is_permissible_move(coords):
            currentUnit = self.get(coords.src)
            destUnit = self.get(coords.dst)
            # logger.info(f"{currentUnit.type.name} at {coords.src} moves in on {coords.dst}.")
            #if destUnit is adversary unit, attack it
            if destUnit is not None and destUnit.player != self.curr_player:
                # print("attacking")
                self.attack_unit(destUnit,currentUnit, coords)
            #if destUnit is same unit, self destruct
            elif destUnit==currentUnit:
                # print("self destructing")
                self.self_destruct(currentUnit, coords)
            #if destUnit is friendly unit, heal
            elif destUnit is not None and destUnit.player == self.curr_player :
                # print("repairing")
                self.repair_unit(destUnit, currentUnit, coords)
            #else, move
            else:
                #update unit position
                for i, pos in enumerate(self.unit_position):
                    if pos == coords.src:
                        self.set_position(coords.dst,i)
                self.set(coords.dst,self.get(coords.src))
                self.set(coords.src,None)      
            
            return (True,"")
        
        return (False,"invalid move")
    # mini max call with no print()
    def perform_move_mini_max(self, coords : CoordPair) -> Tuple[bool,str]:
        """Validate and perform a move expressed as a CoordPair. TODO: WRITE MISSING CODE!!!"""
        if self.is_valid_move_minimax(coords) and self.is_permissible_move_minimax(coords):  
            currentUnit = self.get(coords.src)
            destUnit = self.get(coords.dst)
            #if destUnit is adversary unit, attack it
            if destUnit is not None and destUnit.player != self.curr_player:
                self.attack_unit_mini_max(destUnit,currentUnit, coords)
            #if destUnit is same unit, self destruct
            elif destUnit==currentUnit:
                self.self_destruct_mini_max(currentUnit, coords)
            #if destUnit is friendly unit, heal
            elif destUnit is not None:
                self.repair_unit_mini_max(destUnit, currentUnit, coords)
            #else, move
            else:
                #update unit position
                for i, pos in enumerate(self.unit_position):
                    if pos == coords.src:
                        self.set_position(coords.dst,i)
                self.set(coords.dst,self.get(coords.src))
                self.set(coords.src,None)
            
            return (True,"")
        
        return (False,"invalid move")

    def next_turn(self):
        """Transitions game to the next turn."""
        self.curr_player = self.curr_player.next()
        self.turns_played += 1

    def to_string(self) -> str:
        """Pretty text representation of the game."""
        dim = self.options.dim
        output = ""
        output += f"Current player: {self.curr_player.name}\n"
        output += f"Turns played: {self.turns_played}\n"
        coord = Coord()
        output += "\n   "
        for col in range(dim):
            coord.col = col
            label = coord.col_string()
            output += f"{label:^3} "
        output += "\n"
        for row in range(dim):
            coord.row = row
            label = coord.row_string()
            output += f"{label}: "
            for col in range(dim):
                coord.col = col
                unit = self.get(coord)
                if unit is None:
                    output += " .  "
                else:
                    output += f"{str(unit):^3} "
            output += "\n"
        return output

    def __str__(self) -> str:
        """Default string representation of a game."""
        return self.to_string()
    
    def is_valid_coord(self, coord: Coord) -> bool:
        """Check if a Coord is valid within out board dimensions."""
        dim = self.options.dim
        if coord.row < 0 or coord.row >= dim or coord.col < 0 or coord.col >= dim:
            return False
        return True

    def read_move(self) -> CoordPair:
        """Read a move from keyboard and return as a CoordPair."""
        while True:
            s = input(F'Player {self.curr_player.name}, enter your move: ')
            coords = CoordPair.from_string(s)
            if coords is not None and self.is_valid_coord(coords.src) and self.is_valid_coord(coords.dst):
                return coords
            else:
                pass
                print('Invalid coordinates! Try again.')
    
    def human_turn(self):
        """Human player plays a move (or get via broker)."""
        if self.options.broker is not None:
            print("Getting next move with auto-retry from game broker...")
            while True:
                mv = self.get_move_from_broker()
                if mv is not None:
                    (success,result) = self.perform_move(mv)
                    print(f"Broker {self.curr_player.name}: ",end='')
                    print(result)
                    if success:
                        self.next_turn()
                        break
                sleep(0.1)
        else:
            while True:
                mv = self.read_move()
                (success,result) = self.perform_move(mv)
                if success:
                    print(f"Player {self.curr_player.name}: ",end='')
                    print(result)
                    self.next_turn()
                    break
                else:
                    print("The move is not valid! Try again.")

    def computer_turn(self) -> CoordPair | None:
        """Computer plays a move."""
        mv = self.suggest_move()
        if mv is not None:
            (success,result) = self.perform_move(mv)
            if success:
                print(f"Computer {self.curr_player.name}: ",end='')
                print(result)
                self.next_turn()
        return mv

    def player_units(self, player: Player) -> Iterable[Tuple[Coord,Unit]]:
        """Iterates over all units belonging to a player."""
        for coord in CoordPair.from_dim(self.options.dim).iter_rectangle():
            unit = self.get(coord)
            if unit is not None and unit.player == player:
                yield (coord,unit)

    def is_finished(self) -> bool:
        """Check if the game is over."""
        return self.has_winner() is not None

    def has_winner(self) -> Player | None:
        """Check if the game is over and returns winner"""
        if self.options.max_turns is not None and self.turns_played >= self.options.max_turns:
            #print("Maximum number of turns reached.")
            return Player.Defender
        if self._attacker_has_ai:
            if self._defender_has_ai:
                return None
            else:
                return Player.Attacker    
        return Player.Defender

    def move_candidates(self) -> Iterable[CoordPair]:
        """Generate valid move candidates for the current player."""
        move = CoordPair()
        for (src,_) in self.player_units(self.curr_player):
            move.src = src
            for dst in src.iter_adjacent():
                move.dst = dst
                if self.is_valid_move(move) and self.is_permissible_move(move):
                    yield move.clone()
            move.dst = src
            yield move.clone()

    def random_move(self) -> Tuple[int, CoordPair | None, float]:
        """Returns a random move."""
        random.seed(time.time())
        move_candidates = list(self.move_candidates())
        random.shuffle(move_candidates)
        if len(move_candidates) > 0:
            return (0, move_candidates[0], 1)
        else:
            return (0, None, 0)
    
    def get_e0(self) -> int:
        ls = self.count_player_units()
        e0 = (3*ls[0]+3*ls[1]+3*ls[2]+9999*ls[3])-(3*ls[4]+3*ls[5]+3*ls[6]+9999*ls[7])
        return e0
    
    def count_player_units(self) -> List[int]:
        # player 1 is Attacker, player 2 is defender. Attacker wants to maximize this heuristic and Defender wants to minimize it
        unit_counts = {
            "Virus1": 0,
            "Firewall1": 0,
            "Program1": 0,
            "AI1": 0,
            "Technical2": 0,
            "Firewall2": 0,
            "Program2": 0,
            "AI2": 0
        }
        for coord in CoordPair.from_dim(self.options.dim).iter_rectangle():
            unit = self.get(coord)
            if unit is not None:
                if unit.player == Player.Attacker:
                    if unit.type == UnitType.Virus:
                        unit_counts["Virus1"] += 1
                    elif unit.type == UnitType.Firewall:
                        unit_counts["Firewall1"] += 1
                    elif unit.type == UnitType.Program:
                        unit_counts["Program1"] += 1 
                    else:
                        unit_counts["AI1"] += 1
                else:
                    if unit.type == UnitType.Tech:
                         unit_counts["Technical2"] += 1
                    elif unit.type == UnitType.Firewall:
                        unit_counts["Firewall2"] += 1
                    elif unit.type == UnitType.Program:
                        unit_counts["Program2"] += 1 
                    else:
                        unit_counts["AI2"] += 1  
        return list(unit_counts.values())
    
    def get_e1(self) -> int:
        # player 1 is Attacker, player 2 is defender. This heuristic is related to health, with a focus on harming Defender's AI 
        # Attacker wants to maximize this heuristic and Defender wants to minimize it
        # Attacker wants to protect himself but is more offensive than Defender 
        # Attacker virus can kill defender AI easily. Each unit of health is valued at 60
        # Attacker program can damage defender AI substantially. Each unit of health is valued at 10
        # Attacker AI is important as it can lead to losing the game. Each unit of health is valued at 25
        # Other Attacker pieces are valued at 1 as they are less instrumental to harming the AI
        # The lower the Defender's AI health, the better. Each unit of AI health is valued at 1000/healthOfAI
        # Defender Tech can heal Defender's AI substantially and harm Attacker's Virus majorly.  Each unit of Tech health is valued at 50/healthOfTech
        # Defender Program can  harm Attacker's Virus substantially.  Each unit of Program health is valued at 25/healthOfProgram
        # The other Defender's pieces can be ignored when calculating damge to Attacker
        ls = self.count_player_health()
        e1 = 600*ls[0]+ls[1]+10*ls[2]+25*ls[3]
        if ls[4]!=0:
            e1 += 100/ls[4]
        else:
            e1 += 150
        if ls[5]!=0:
            e1 += 50/ls[5]
        else:
            e1 += 100
        if ls[6]!=0:
            e1 += 2000/ls[6]
        else:
            e1 += 9000
        return e1
    
    def count_player_health(self) -> List[int]:   
        unit_health_count = {
            "Virus1": 0,
            "Firewall1": 0,
            "Program1": 0,
            "AI1": 0,
            "Technical2": 0,
            "Program2": 0,
            "AI2": 0
        }
        for coord in CoordPair.from_dim(self.options.dim).iter_rectangle():
            unit = self.get(coord)
            if unit is not None:
                if unit.player == Player.Attacker:
                    if unit.type == UnitType.Virus:
                        unit_health_count["Virus1"] += unit.health
                    elif unit.type == UnitType.Firewall:
                        unit_health_count["Firewall1"] +=unit.health
                    elif unit.type == UnitType.Program:
                        unit_health_count["Program1"] += unit.health
                    else:
                        unit_health_count["AI1"] +=  unit.health
                else:
                    if unit.type == UnitType.Tech:
                         unit_health_count["Technical2"] += unit.health
                    elif unit.type == UnitType.Program:
                        unit_health_count["Program2"] += unit.health
                    elif unit.type==UnitType.AI:
                        unit_health_count["AI2"] += unit.health
        return list(unit_health_count.values())
    
    def get_e2(self) -> int:
        # player 1 is Attacker, player 2 is defender. This heuristic is related to Attacker's unit distancce to Defender's AI
        # Attacker wants to maximize this heuristic and Defender wants to minimize it [Attacker maximizes the inverse of the distance]
        # Attacker wants to protect himself but is more offensive than Defender 
        # Attacker virus can kill defender AI easily. Distance of 1 is preferable. 1000/distanceOfAVtoDA
        # Attacker program can damage defender AI substantially. 500/distanceOfAPtoDA
        # we dont want the Attacker AI close to defender's AI as it is dangerous and may lead to losing the game. 5*distanceOfAAtoDA 
        # The less friendly units are close to the Defender's AI, the better
        # Defender Tech can heal Defender's AI substantially and harm Attacker's Virus majorly.  Each unit of Tech distance is valued at 60*distanceDTtoDA
        # Defender Program can  harm Attacker's Virus substantially.  Each unit of Program health is valued at 30*distanceDPtoAV
        # Defender Program can  harm Attacker's AI substantially.  Each unit of Program health is valued at 30*distanceDPtoAV
        # The other Defender's or Attacker pieces can be ignored
        ls = self.get_distance_from_units()
        e2 = 30*ls[5]+30*ls[1]+60*ls[2]+60*ls[7]+5*ls[4]
        if ls[3]!=0:
            e2+=500/ls[3]
        if ls[0]!=0:
            e2+=1000/ls[3]           
        return e2
    
    def get_distance_from_units(self):
        #Distances from Attacker to defender
        unit_distance_count = {
            "AttackerVirustoDefenderAI": 0, #0
            "AttackerVirustoDefenderProgram": 0,#1
            "AttackerVirustoDefenderTech": 0,#2
            
            "AttackerProgramtoDefenderAI": 0,#3
            
            "AttackerAItoDefenderAI": 0,#4
            "AttackerAItoDefenderProgram": 0, #5      
            
            "AttackerFirewalltoDefenderAI": 0,#6
            
            "DefenderAItoDefenderTech": 0 #7
        }
        visitedCoord = set()
        for i, coord1 in enumerate(self.unit_position):
            for j, coord2 in enumerate(self.unit_position):
                if i != j and coord1 is not None and coord2 is not None:
                    distance = coord1.manhattan_distance(coord2)
                    visited_coordpair1 = (coord1, coord2)
                    visited_coordpair2 = (coord2, coord1)
                    
                    if visited_coordpair1 not in visitedCoord and visited_coordpair2 not in visitedCoord :
                        if self.get(coord1).player == Player.Attacker and self.get(coord2).player == Player.Defender:
                            key = f"{self.get(coord1).player}{self.get(coord1).player}to{self.get(coord2).player}{self.get(coord2).player}"
                            if key in unit_distance_count:
                                unit_distance_count[key] += distance
                                visitedCoord.add(visited_coordpair1)
                                visitedCoord.add(visited_coordpair2)
                        
                        elif self.get(coord1).player == Player.Defender and self.get(coord2).player == Player.Defender:
                            key = f"{self.get(coord1).player}{self.get(coord1).player}to{self.get(coord2).player}{self.get(coord2).player}"
                            if key in unit_distance_count:
                                unit_distance_count[key] += distance
                                visitedCoord.add(visited_coordpair1)
                                visitedCoord.add(visited_coordpair2)     
        
        return list(unit_distance_count.values())                              
                    
    def minimax (self,  depth: int, maximizingPlayer: bool)-> dict[CoordPair, int]:
        self.stats.evaluations_per_depth[self.options.max_depth-depth]+=1
        time_difference = datetime.now() - self.start_time
        if depth == 0 or time_difference.seconds > self.options.max_time - 0.05:
            if(self.options.heuristic == 0):
                 return (None, self.get_e0())
            elif(self.options.heuristic == 1):
                return (None, self.get_e1())
            else:
                 return (None, self.get_e2()+self.get_e1())
        elif self.is_finished():
            winner = self.has_winner()
            if winner==Player.Attacker:
                return (None, MAX_HEURISTIC_SCORE)
            else:
                return (None,MIN_HEURISTIC_SCORE)
        elif maximizingPlayer: #Attacker
            value = MIN_HEURISTIC_SCORE
            bestmove = self.random_move()[1]
            cand = list(self.move_candidates())
            self.listOfCandidateMove.append(len(cand))
            for move in self.move_candidates():
                gameCopy = self.clone()
                gameCopy.perform_move_mini_max(move)
                #we do this as to not increment the number of turns played during minimax
                gameCopy.curr_player = gameCopy.curr_player.next()
                newScore= gameCopy.minimax((depth-1), False)[1]
                if newScore>value:
                    value=newScore
                    bestmove = move
            return (bestmove, value)
        else: #minimizing player so Deffender
            value = MAX_HEURISTIC_SCORE
            bestmove = self.random_move()[1]
            cand = list(self.move_candidates())
            self.listOfCandidateMove.append(len(cand))
            for move in self.move_candidates():
                gameCopy = self.clone()
                gameCopy.perform_move_mini_max(move)
                gameCopy.curr_player = gameCopy.curr_player.next()
                newScore= gameCopy.minimax((depth-1), True)[1]
                if newScore<value:
                        value=newScore
                        bestmove = move
            return (bestmove, value)
            
    def minimax_alpha_beta (self,  depth: int, alpha: int, beta: int, maximizingPlayer: bool)-> dict[CoordPair, int]:
        self.stats.evaluations_per_depth[self.options.max_depth-depth]+=1
        time_difference = datetime.now() - self.start_time
        if depth == 0 or time_difference.seconds > self.options.max_time - 0.05:
            if(self.options.heuristic == 0):
                return (None, self.get_e0())
            elif(self.options.heuristic == 1):
                return (None, self.get_e1())
            else:
                return (None, self.get_e2()+self.get_e1())
        elif self.is_finished():
            winner = self.has_winner()
            if winner==Player.Attacker:
                return (None, MAX_HEURISTIC_SCORE)
            else:
                return (None,MIN_HEURISTIC_SCORE)
        elif maximizingPlayer: #Attacker
            value = MIN_HEURISTIC_SCORE
            bestmove = self.random_move()[1]
            cand = list(self.move_candidates())
            self.listOfCandidateMove.append(len(cand))
            for move in self.move_candidates():
                gameCopy = self.clone()
                gameCopy.perform_move_mini_max(move)
                #we do this as to not increment the number of turns played during minimax-alpha-beta
                gameCopy.curr_player = gameCopy.curr_player.next()
                newScore= gameCopy.minimax_alpha_beta((depth-1), alpha, beta, False)[1]
                if newScore>value:
                    value=newScore
                    bestmove = move
                alpha = max(alpha, value)
                if beta <= alpha:
                    break
            return (bestmove, value)
        else: #minimizing player so Defender
            value = MAX_HEURISTIC_SCORE
            bestmove = self.random_move()[1]
            cand = list(self.move_candidates())
            self.listOfCandidateMove.append(len(cand))
            for move in self.move_candidates():
                gameCopy = self.clone()
                gameCopy.perform_move_mini_max(move)
                gameCopy.curr_player = gameCopy.curr_player.next()
                newScore= gameCopy.minimax_alpha_beta((depth-1), alpha, beta, True)[1]
                if newScore<value:
                        value=newScore
                        bestmove = move
                beta = min(beta, value)
                if beta <= alpha:
                    break
            return (bestmove, value)
     
    def suggest_move(self) -> CoordPair | None:
        """Suggest the next move using minimax alpha beta. TODO: REPLACE RANDOM_MOVE WITH PROPER GAME LOGIC!!!"""
        self.start_time = datetime.now()
        maximizing = self.curr_player == Player.Attacker
        if(self.options.alpha_beta):
            (move, score)= self.minimax_alpha_beta(self.options.max_depth, MIN_HEURISTIC_SCORE,MAX_HEURISTIC_SCORE, maximizing)
        else:
            (move, score)= self.minimax(self.options.max_depth,maximizing)
        elapsed_seconds = (datetime.now() - self.start_time).total_seconds()
        self.stats.total_seconds += elapsed_seconds
        total_evals = sum(self.stats.evaluations_per_depth.values())
        print(f"Heuristic score: {score}")
        print(f"Cumulative evals: {total_evals} ",end='')
        print("\n")
        print(f"Evals per depth: ",end='')
        for k in sorted(self.stats.evaluations_per_depth.keys()):
            print(f"{k}:{self.stats.evaluations_per_depth[k]} ",end='')
        print("\n")
        print("Cumulative % evals by depth:")
        for k in sorted(self.stats.evaluations_per_depth.keys()):
            print(f"{k}:{self.stats.evaluations_per_depth[k]/total_evals*100:0.1f}% ",end='')
        if self.stats.total_seconds > 0:
            print("\n")
            print(f"Eval perf.: {total_evals/self.stats.total_seconds/1000:0.1f}k/s")
        print(f"Elapsed time: {elapsed_seconds:0.1f}s")
        average = sum(self.listOfCandidateMove) /len(self.listOfCandidateMove)
        print(f"Average Branching Factor: {average:0.2f}")
        return move

    def post_move_to_broker(self, move: CoordPair):
        """Send a move to the game broker."""
        if self.options.broker is None:
            return
        data = {
            "from": {"row": move.src.row, "col": move.src.col},
            "to": {"row": move.dst.row, "col": move.dst.col},
            "turn": self.turns_played
        }
        try:
            r = requests.post(self.options.broker, json=data)
            if r.status_code == 200 and r.json()['success'] and r.json()['data'] == data:
                print(f"Sent move to broker: {move}")
                pass
            else:
                print(f"Broker error: status code: {r.status_code}, response: {r.json()}")

        except Exception as error:
            print(f"Broker error: {error}")

    def get_move_from_broker(self) -> CoordPair | None:
        """Get a move from the game broker."""
        if self.options.broker is None:
            return None
        headers = {'Accept': 'application/json'}
        try:
            r = requests.get(self.options.broker, headers=headers)
            if r.status_code == 200 and r.json()['success']:
                data = r.json()['data']
                if data is not None:
                    if data['turn'] == self.turns_played+1:
                        move = CoordPair(
                            Coord(data['from']['row'],data['from']['col']),
                            Coord(data['to']['row'],data['to']['col'])
                        )
                        print(f"Got move from broker: {move}")
                        return move
                    else:
                        print("Got broker data for wrong turn.")
                        print(f"Wanted {self.turns_played+1}, got {data['turn']}")
                else:
                    print("Got no data from broker")
            else:
                print(f"Broker error: status code: {r.status_code}, response: {r.json()}")
        except Exception as error:
            print(f"Broker error: {error}")
        return None

##############################################################################################################

def main():
    # parse command line arguments
    parser = argparse.ArgumentParser(
        prog='ai_wargame',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--max_depth', type=int, help='maximum search depth')
    parser.add_argument('--max_time', type=float, help='maximum search time')
    parser.add_argument('--game_type', type=str, default="manual", help='game type: auto|attacker|defender|manual')
    parser.add_argument('--broker', type=str, help='play via a game broker')
    parser.add_argument('--max_turns', type=int, help='maximum turns' )
    parser.add_argument('--heuristic', type=int, help='chosen heuristic' )
    parser.add_argument('--alpha_beta', type=str, help='alpha beta' )
    args = parser.parse_args()

    # parse the game type
    if args.game_type == "attacker":
        game_type = GameType.AttackerVsComp
    elif args.game_type == "defender":
        game_type = GameType.CompVsDefender
    elif args.game_type == "manual":
        game_type = GameType.AttackerVsDefender
    else:
        game_type = GameType.CompVsComp

    # set up game options
    options = Options(game_type=game_type)

    # override class defaults via command line options
    if args.max_depth is not None:
        options.max_depth = args.max_depth
    if args.max_time is not None:
        options.max_time = args.max_time
    if args.broker is not None:
        options.broker = args.broker
    if args.max_turns is not None:
        options.max_turns = args.max_turns
    if args.heuristic is not None:
        options.heuristic = args.heuristic
    if args.alpha_beta is not None:
        if args.alpha_beta.lower() == "false":
            options.alpha_beta = False

    # create a new game
    game = Game(options=options)
    for i in range(0,game.options.max_depth+1):
        game.stats.evaluations_per_depth[i] = 0
    logFileName = f"gameTrace-{options.alpha_beta}-{options.max_time}-{options.max_turns}"
    logging.basicConfig(filename=logFileName,format='%(message)s', level=logging.INFO)
    
    gameParameters = f"""The value of the timeout is {options.max_time} seconds.\nThe max number of turns {options.max_turns}.\nThe game type is {game_type.name}. """
    
    logger.info(gameParameters)
    # the main game loop
    while True:
        print()
        print(game)
        logger.info(f"\n{game}")
        winner = game.has_winner()
        if winner is not None:
            winningMessage = f"{winner.name} wins!"
            print(winningMessage)
            logger.info(winningMessage)
            break
        if game.options.game_type == GameType.AttackerVsDefender:
            game.human_turn()
        elif game.options.game_type == GameType.AttackerVsComp and game.curr_player == Player.Attacker:
            game.human_turn()
        elif game.options.game_type == GameType.CompVsDefender and game.curr_player == Player.Defender:
            game.human_turn()
        else:
            player = game.curr_player
            move = game.computer_turn()
            if move is not None:
                game.post_move_to_broker(move)
            else:
                print("Computer doesn't know what to do!!!")
                exit(1)
    logger.info(f"Game ended after {game.turns_played} turns")
    logging.shutdown()
##############################################################################################################

if __name__ == '__main__':
    main()
