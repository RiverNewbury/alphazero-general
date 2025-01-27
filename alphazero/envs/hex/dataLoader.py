description = """{-
Module      : DataHandler
Description : Manipulating the data from Games and Moves into better form
Maintainer  : River

In games.csv
--------------------------------------------------------------------
"gid" is just unique ID for game,
"boardSize" is size of the board played on,
"moves" is total number of moves played,
"result" is 0 if first player lost 2 if they won,
"rating", "rating" are the ratings of the 2 players in some order

In moves.csv
--------------------------------------------------------------------
"gid" is just unqiue ID for game linking to games.csv,
"nmove" is what number move it is (i.e 1 up to moves),
"jmove" is the move taken
    - resign is let other player win
    - swap is swap position not colour! For example game: https://www.littlegolem.net/jsp/game/game.jsp?gid=771&nmove=2
    - ge is (4,6) i.e reverse(chr(_) for i in "ge") <- OLD CHANGE

-}"""


#-------- Imports ---------------------------------------------------------------
import torch
from alphazero.envs.hex.hex import Game, BOARD_SIZE, CANONICAL_STATE
import numpy as np
from alphazero.utils import get_iter_file
from torch import multiprocessing as mp
from queue import Empty
import os
import pickle

#-------- Classes ---------------------------------------------------------------

#-------- Datatypes -------------------------------------------------------------

#-------- Destructors -----------------------------------------------------------

#-------- Helper Functions ------------------------------------------------------

#-------- Main Functions --------------------------------------------------------

def saveIterationSamples(iteration, output, game_cls):
    num_samples = output.qsize()
    print(f'Saving {num_samples} samples')

    obs_size = game_cls.observation_size()
    data_tensor = torch.zeros([num_samples, *obs_size])        
    policy_tensor = torch.zeros([num_samples, game_cls.action_size()])
    value_tensor = torch.zeros([num_samples, game_cls.num_players() + game_cls.has_draw()])
    for i in range(num_samples):
        data, policy, value = output.get()
        data_tensor[i] = torch.from_numpy(data)
        policy_tensor[i] = torch.from_numpy(policy)
        value_tensor[i] = torch.from_numpy(value)

    folder = "data/human"
    filename = os.path.join(folder, get_iter_file(iteration).replace('.pkl', ''))
    if not os.path.exists(folder): os.makedirs(folder)

    torch.save(data_tensor, filename + '-data.pkl', pickle_protocol=pickle.HIGHEST_PROTOCOL)
    torch.save(policy_tensor, filename + '-policy.pkl', pickle_protocol=pickle.HIGHEST_PROTOCOL)
    torch.save(value_tensor, filename + '-value.pkl', pickle_protocol=pickle.HIGHEST_PROTOCOL)
    del data_tensor
    del policy_tensor
    del value_tensor

def main():
    assert(BOARD_SIZE == 13)
    data = [[], [], [], [], [], [], [], [], [], [], [], [], [], []]
    totalMoves = 0
    with open('data/hex/games.csv') as games:
        with open('data/hex/moves.csv') as moves:
            # skip past unnecessary headers
            games.readline()
            moves.readline() 

            game = games.readline()
            move = moves.readline().split(',')
            while game:
                gameSplit = game.split(',')
                gID       = int(gameSplit[0])
                boardSize = int(gameSplit[1])
                nMoves    = int(gameSplit[2])
                result    = int(gameSplit[3])
                r1        = float(gameSplit[4])
                r2        = float(gameSplit[5])
                moveList  = []


                while True:
                    #print(move)
                    try:
                        gID2 = int(move[0])
                    except:
                        break;
                    mv   = move[2]
                    if (gID2 != gID):
                        break;
                    
                    if len(mv) == 5:
                        cords = (ord(mv[1]) - ord('a'), ord(mv[2]) - ord('a'))
                        moveList.append(cords)
                    elif (mv[1:-2] == "swap"):
                        cords = (-10,-10)
                        moveList.append(cords)

                    move = moves.readline().split(',')

                if boardSize == 13 and len(moveList) > 2 and (r1 > 1200 or r2 > 1200):
                    totalMoves += len(moveList)
                    data[(max(int(r1),int(r2))-1200)//100].append((gID, result, r1, r2, moveList))
                game = games.readline()
    #print(totalMoves/len(data))
    #print(len(data))
    #maximum = 2600
    for i in data:
        print(len(i))
    #for i in range(1000, 2600, 200):
    #    databetween = list(filter(lambda x: max(x[2],x[3])>= i and max(x[2],x[3])< i+200, data))
    #    print("num data points between {} and {} is {}".format(i, i+200, len(databetween)))
    
    # sort by max of the 2 ratings
    #data.sort(key = lambda x: max(x[2],x[3]))
    #assert False
    #print(max(map(lambda x : x[2], data)))
    #print(max(map(lambda x : x[3], data)))
    
    print("Loaded")
    game_cls = Game
    i = 0
    for data1 in data:
        print(len(data1))
        out = mp.Queue()
        n = 0
        for gID, result, r1, r2, moveList in data1:
            n+=1
            #if (n < 2) : continue
            #print(moveList)
            #print(n)
            g = game_cls()
            if moveList[1] == (-10, -10):
                winstate = np.array([result == 0,result == 2])
            else:        
                winstate = np.array([result == 2,result == 0])
            #print(winstate)

            for moveNumber, move in enumerate(moveList):
                #print(move)
                if (move == (-10, -10)):
                    continue;
                else:
                    if CANONICAL_STATE and g._player == 1:
                        move = g._board.pairflipInXPlusYCorrection(move)

                    if moveList[1] == (-10, -10) and moveNumber == 0:
                        #print(move)
                        move = (move[1],move[0])
                        #print(move)

                    trueMove = (move[1]) * 13 + (move[0])
                assert (trueMove>=0 and trueMove<=15*15)
                # Maybe Add noise?
                pi = np.zeros(13*13+1, dtype=np.float32)
                pi[trueMove] = 1

                #print(g._board)
                #print(g._board)
                if moveNumber>=2:
                    #----------------------
                    data = g.symmetries(pi, winstate)
                    for state, pi, true_winstate in data:
                        #print(state.observation(), pi, np.array(true_winstate, dtype=np.float32))
                        out.put((
                            state.observation(), pi, np.array(true_winstate, dtype=np.float32)
                        ))
                    g.play_action(trueMove)
            if n%100 == 0:
                print('.', end = '', flush=True)
            if n%5000 == 0:
                print()
        saveIterationSamples(i, out, game_cls)
        i +=1


if __name__ == "__main__":
    print(description)
    main()
