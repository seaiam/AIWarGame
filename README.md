[![Typing SVG](https://readme-typing-svg.demolab.com?font=Roboto&weight=800&size=30&pause=1000&color=5F735A&center=true&width=435&lines=Welcome+to+AIWar+Game+!)](https://git.io/typing-svg)

## :clipboard:Description
<p style='text-align: justify;'>
  Welcome to our AI War Game! The goal is simple, protect your AI unit at all cost !
</p>

## :hammer_and_wrench:Language 
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)

## :woman_technologist:Team members

 | Name | Student ID | GitHub Username | 
| :---           | :---          | :---          | 
 Fatima El Fouladi     | 40108832    | seaiam    |
Anum Siddiqui     | 40129811    | AnumSidd    | 
 Raya Maria Lahoud     | 40129965    | rayalahoud    |
 
## :computer: How to run the game
**On Mac OS**
 1. Clone the repository
 2. run ``python3 -m venv venv`` NOTE: could be python instead of python3
 3. activate virtual environment by running ```source venv/bin/activate```
4. run the game  ```python wargame.py```. You can add game settings as we will see later.


**On Windows**
 1. Clone the repository 
 2. run ``python3 -m venv venv`` NOTE: could be python instead of python3
 3. activate virtual environment by running ```venv\Scripts\activate```
 4. run the game  ```python wargame.py```. You can add game settings as we will see later.

## :video_game: How to play the game !
### Game settings
<p style='text-align: justify;'>
  <ul>
    <li>
      <b>game_type</b>: By default, this is human vs human. The types are : auto, attacker, defender, manual
    </li>
    <li>
      <b>max_time</b>: How long the algorithm can take to make a decision. By default, this is 5.0 seconds
    </li>
    <li>
      <b>max_turns</b>: How many turns the game can have. If we reach the max, Defender automatically wins. By default, this is 100
    </li>
    <li>
        <b>heuristic</b>: Which of our 3 heuristics will the algorithm use for the mini-max algorithm? By default, it is 0: ie the least informed heuristic. 
    </li>
      <li>
        <b>alpha_beta</b>: Will the algorithm use alpha-beta pruning to optimize its search? By default, this is set to True.
    </li>
    <li>
        <b>max_depth</b>: How deep in the search tree will the mini-max algorithm go? By default, this is set to 4
    </li>
  </ul>
</p>
          
### Allowed moves

1. The destination must be free (no other unit is on it).
2. Units are said to be engaged in combat if an adversarial unit is adjacent (in any of the 4 directions).
If an AI, a Firewall or a Program is engaged in combat, they cannot move.
The Virus and the Tech can move even if engaged in combat.
3. The attacker’s AI, Firewall and Program can only move up or left.
The Tech and Virus can move left, top, right, bottom.
4. The defender’s AI, Firewall and Program can only move down or right.
The Tech and Virus can move left, top, right, bottom.

### Damage Table
For a unit S attacking a unit T. Damage is bidirectional. <br>
<img width="460" alt="Screenshot 2024-01-16 at 11 40 47 AM" src="https://github.com/seaiam/AIWarGame/assets/65039814/6efedb99-ef9a-463b-898f-45ea9824ef2b"> <br>
Note that units can self-destruct and give 2 units of damage to every adjacent unit, including friendly ones.

### Repair Table
For a unit S healing a friendly unit T. <br>
<img width="460" alt="Screenshot 2024-01-16 at 11 41 21 AM" src="https://github.com/seaiam/AIWarGame/assets/65039814/4a418f21-493a-40f1-9635-9273e63a66d3">
