"""
This is out main driver file. It will be responsible for handling user input and displaying the current GameState object.
"""

import pygame as p
import ChessEngine, SmartMoveFinder
from multiprocessing import Process, Queue
import queue

BOARD_WIDTH = BOARD_HEIGHT = 512 # 400 is another option
MOVE_LOG_PANEL_WIDTH = 250
MOVE_LOG_PANEL_HEIGHT = BOARD_HEIGHT
DIMENSION = 8 # dimensions of a chess board are 8 x 8
SQ_SIZE = BOARD_HEIGHT // DIMENSION
MAX_FPS = 15 # for animations later on
IMAGES = {}

'''
Initialize a global dictionary of images. This will be called exactly once in the main
'''
def loadImages():
    pieces = ['wp', 'wR', 'wN', 'wB', 'wK', 'wQ', 'bp', 'bR', 'bN', 'bB', 'bK', 'bQ']
    for piece in pieces:
        IMAGES[piece] = p.transform.scale(p.image.load("images/" + piece + ".png"), (SQ_SIZE, SQ_SIZE))
    # Note: we can access an image by saying 'IMAGES['wp']'

'''
The main driver for out code. This will handle user input and updating the graphics
'''

def main():
    p.init()
    screen = p.display.set_mode((BOARD_WIDTH + MOVE_LOG_PANEL_WIDTH, BOARD_HEIGHT))
    clock = p.time.Clock()
    screen.fill(p.Color("white"))
    moveLogFont = p.font.SysFont("Arial", 14, False, False)
    gs = ChessEngine.GameState()
    validMoves = gs.getValidMoves()
    moveMade = False # flag variable for wen a move is made
    animate = False # flag variable for when we should animate a move
    print(gs.board)
    loadImages() # only do this onces, before the while loop
    running = True
    sqSelected = () # no square is selected, kep track of the last click of the user (tuple: (row, col))
    playerClicks = [] # keeps track of player clicks (two tuples: [(6, 4), (4, 4)])
    gameOver = False
    playerOne = True # if human isi playing white, then this will be True. If an AI is playing then false
    playerTwo = True # same as above but for black
    AIThinking = False
    moveFinderProcess = None
    moveUndone = False

    while running:
        humanTurn = (gs.whiteToMove and playerOne) or (not gs.whiteToMove and playerTwo)
        for e in p.event.get():
            if e.type == p.QUIT:
                running = False
            #mouse handler
            elif e.type == p.MOUSEBUTTONDOWN:
                if not gameOver:
                    location = p.mouse.get_pos() # (x, y) location of mouse
                    col = location[0] // SQ_SIZE 
                    row = location[1] // SQ_SIZE
                    if sqSelected == (row, col) or col >= 8: # the user clicked the same square twice or user clicked mouse log
                        sqSelected = () #deselect
                        playerClicks = [] # clear player clicks
                    else:
                        sqSelected = (row, col)
                        playerClicks.append(sqSelected) # append for both 1st and 2nd clicks
                    if len(playerClicks) == 2 and humanTurn: # after 2nd click
                        move = ChessEngine.Move(playerClicks[0], playerClicks[1], gs.board)
                        print(move.getChessNotation())

                        moveFound = False

                        for validMove in validMoves:
                            if move == validMove:
                                # print("Castle move:", validMove.castle)
                                # print(validMove.getChessNotation())
                                if validMove.pawnPromotion:
                                    validMove.promotionChoice = getPromotionChoice(screen, gs.whiteToMove)
                                gs.makeMove(validMove)
                                moveMade = True
                                moveFound = True
                                animate = True
                                sqSelected = () # reset user clicks
                                playerClicks = []
                                break
                        if not moveFound:
                            playerClicks = [sqSelected] 
            #key handlers
            elif e.type == p.KEYDOWN:
                if e.key == p.K_z: # undo when 'z' is pressed
                    gs.undoMove()
                    moveMade = True
                    animate = False
                    gameOver = False
                    if AIThinking:
                        moveFinderProcess.terminate()
                        AIThinking = False
                    moveUndone = True
                if e.key == p.K_r: # reset the game when 'r' is pressed
                    gs = ChessEngine.GameState()
                    validMoves = gs.getValidMoves() 
                    sqSelected = ()
                    playerClicks = []
                    moveMade = False
                    animate = False
                    gameOver = False
                    if AIThinking:
                        moveFinderProcess.terminate()
                        AIThinking = False
                    moveUndone = True

        # AI move finder, Greedy Algorithm
        # if not gameOver and not humanTurn:
        #     AIMove = SmartMoveFinder.findBestMove(gs, validMoves)
        #     if AIMove is None:
        #         AIMove = SmartMoveFinder.findRandomMove(validMoves)
        #     gs.makeMove(AIMove)
        #     moveMade = True
        #     animate = True

        # if moveMade:
        #     if animate:
        #         animateMove(gs.moveLog[-1], screen, gs.board, clock)
        #     validMoves = gs.getValidMoves()
        #     moveMade = False
        #     animate = False

        # drawGameState(screen, gs, validMoves, sqSelected)

        # if gs.checkMate:
        #     gameOver = True
        #     if gs.whiteToMove:
        #         drawText(screen, "Black wins by CheckMate")
        #     else:
        #         drawText(screen, "White wins by CheckMate")
        # elif gs.staleMate:
        #     gameOver = True
        #     drawText(screen, "StaleMate")

        # AI move finder, MinMax Algorithm
        if not gameOver and not humanTurn and not moveUndone:
            if not AIThinking:
                AIThinking = True 
                print("Thinking...")
                returnQueue = Queue() # used to pass data between threads
                moveFinderProcess = Process(target = SmartMoveFinder.findBestMove, args=(gs, validMoves, returnQueue))
                moveFinderProcess.start() # call findBestMove(gs, validMoves, returnQueue)
                # AIMove = SmartMoveFinder.findBestMove(gs, validMoves)

            if not moveFinderProcess.is_alive():
                print("Done thinking")
                try:
                    AIMove = returnQueue.get(timeout=0.1)
                except queue.Empty:
                    AIMove = None
                if AIMove is None:
                    AIMove = SmartMoveFinder.findRandomMove(validMoves)
                gs.makeMove(AIMove)
                moveMade = True
                animate = True
                AIThinking = False 

        if moveMade:
            if animate:
                animateMove(gs.moveLog[-1], screen, gs.board, clock)
            validMoves = gs.getValidMoves()
            moveMade = False
            animate = False
            moveUndone = False

        drawGameState(screen, gs, validMoves, sqSelected, moveLogFont)

        if gs.checkMate or gs.staleMate:
            gameOver = True
            if gs.staleMate:
                text = 'Stalemate'
            else:
                text = 'Black Wins by Checkmate!' if gs.whiteToMove else 'White wins by CheckMate!'
            drawEndGameText(screen, text)
            

        clock.tick(MAX_FPS)
        p.display.flip()

'''
Responsible for all the graphics within a current game state
'''
def drawGameState(screen, gs, validMoves, sqSelected, moveLogFont):
    drawBoard(screen) # draw squares on the board
    highlightSquares(screen, gs, validMoves, sqSelected)
    # add in piece highlighting or move suggestions (later)

    drawPieces(screen, gs.board) # draw pieces on top of those squares
    drawMoveLog(screen, gs, moveLogFont)

'''
Draw the squares on the board. The top left square is always light
'''
def drawBoard(screen):
    global colors
    colors = [p.Color("white"), p.Color("gray")]
    for r in range(DIMENSION):
        for c in range(DIMENSION):
            color = colors[((r+c)%2)]
            p.draw.rect(screen, color, p.Rect(c*SQ_SIZE, r* SQ_SIZE, SQ_SIZE, SQ_SIZE))

"""
Highlighting the square selected and moves for piece selected
"""
def highlightSquares(screen, gs, validMoves, sqSelected):
    # Highlight the king in check, regardless of what's currently selected
    if gs.inCheck and not (gs.checkMate or gs.staleMate):
        kingRow, kingCol = gs.whiteKingLocation if gs.whiteToMove else gs.blackKingLocation
        s = p.Surface((SQ_SIZE, SQ_SIZE))
        s.set_alpha(150)
        s.fill(p.Color('red'))
        screen.blit(s, (kingCol*SQ_SIZE, kingRow*SQ_SIZE))

    if sqSelected != (): 
        r, c = sqSelected # reference to row and column of the square selected
        if gs.board[r][c][0] == ('w' if gs.whiteToMove else 'b'): #sqSelected is a piece that can be moved
            # highlight selected square
            s = p.Surface((SQ_SIZE, SQ_SIZE))
            s.set_alpha(100) # transparencyc value -> 0 transaprent; 255 opaque
            s.fill(p.Color('blue'))
            screen.blit(s, (c*SQ_SIZE, r*SQ_SIZE))
            # highlight moves from that square
            s.fill(p.Color('yellow'))
            for move in validMoves:
                if move.startRow == r and move.startCol == c:
                    screen.blit(s, (SQ_SIZE*move.endCol, move.endRow*SQ_SIZE))

'''
Draw the pieces on the board using the current GameState.board
'''
def drawPieces(screen, board):
    for r in range(DIMENSION):
        for c in range(DIMENSION):
            piece = board[r][c]
            if piece != "--": # not empty square
                screen.blit(IMAGES[piece], p.Rect(c*SQ_SIZE, r*SQ_SIZE, SQ_SIZE, SQ_SIZE))

'''
Draws the move log
'''
def drawMoveLog(screen, gs, font):
    moveLogRect = p.Rect(BOARD_WIDTH, 0, MOVE_LOG_PANEL_WIDTH, MOVE_LOG_PANEL_HEIGHT)
    p.draw.rect(screen, p.Color("black"), moveLogRect)
    moveLog = gs.moveLog
    moveTexts = []
    for i in range(0, len(moveLog), 2):
        moveString = str(i//2 + 1) + ". " + str(moveLog[i]) + " "
        if i+1 < len(moveLog): #make sure black made a move
            moveString += str(moveLog[i+1]) + "  "
        moveTexts.append(moveString)

    movesPerRow = 3
    padding = 5
    lineSpacing = 2
    textY = padding
    for i in range(0, len(moveTexts), movesPerRow):
        text = ""
        for j in range(movesPerRow):
            if i+j < len(moveTexts):
                text += moveTexts[i+j]
        textObject = font.render(text, True, p.Color('white'))
        textLocation = moveLogRect.move(padding, textY)
        screen.blit(textObject, textLocation)
        textY += textObject.get_height() + lineSpacing

    # status banner: whose turn is in check, if any
    if gs.inCheck and not (gs.checkMate or gs.staleMate):
        bannerHeight = 36
        bannerRect = p.Rect(BOARD_WIDTH, MOVE_LOG_PANEL_HEIGHT - bannerHeight,
                             MOVE_LOG_PANEL_WIDTH, bannerHeight)
        p.draw.rect(screen, p.Color("firebrick"), bannerRect)
        checkFont = p.font.SysFont("Arial", 20, True, False)
        who = "White" if gs.whiteToMove else "Black"
        checkSurf = checkFont.render(f"{who} is in CHECK!", True, p.Color("white"))
        checkLocation = checkSurf.get_rect(center=bannerRect.center)
        screen.blit(checkSurf, checkLocation)

"""
Animating a move
"""
def animateMove(move, screen, board, clock):
    global colors
    dR = move.endRow - move.startRow
    dC = move.endCol - move.startCol
    framesperSquare = 10 # frames to move one square
    frameCount = (abs(dR) + abs(dC))* framesperSquare
    for frame in range(frameCount + 1):
        r, c = (move.startRow + dR*frame/frameCount, move.startCol + dC*frame/frameCount)
        drawBoard(screen)
        drawPieces(screen, board)
        # erase the piece moved from its ending square
        color = colors[(move.endRow + move.endCol) % 2]
        endSquare = p.Rect(move.endCol*SQ_SIZE, move.endRow*SQ_SIZE, SQ_SIZE, SQ_SIZE)
        p.draw.rect(screen, color, endSquare)
        # draw captured piece onto rectange
        if move.pieceCaptured != "--":
            if move.enPassant:
                enPassantRow = move.endRow + 1 if move.pieceCaptured[0] == 'b' else move.endRow - 1
                endSquare = p.Rect(move.endCol * SQ_SIZE, enPassantRow * SQ_SIZE, SQ_SIZE, SQ_SIZE)
            screen.blit(IMAGES[move.pieceCaptured], endSquare)
        # draw moving piece
        if move.pieceMoved != '--':
            screen.blit(IMAGES[move.pieceMoved], p.Rect(c*SQ_SIZE, r*SQ_SIZE, SQ_SIZE, SQ_SIZE))
        p.display.flip()
        clock.tick(60)

"""
Blocks (with its own small event loop) until the human clicks one of Q/R/B/N,
then returns that letter. Only ever called for the human's own real move —
the AI's simulated moves during search always keep Move's default 'Q'.
"""
def getPromotionChoice(screen, whiteToMove):
    color = 'w' if whiteToMove else 'b'
    options = [('Q', 'Queen'), ('R', 'Rook'), ('B', 'Bishop'), ('N', 'Knight')]

    titleFont = p.font.SysFont("Arial", 22, True, False)
    labelFont = p.font.SysFont("Arial", 14, False, False)

    boxSize = SQ_SIZE
    gap = 16
    labelHeight = 22
    titleHeight = 40

    totalWidth = boxSize * len(options) + gap * (len(options) + 1)
    panelHeight = titleHeight + boxSize + labelHeight + gap * 2
    panelRect = p.Rect(0, 0, totalWidth, panelHeight)
    panelRect.center = (BOARD_WIDTH // 2, BOARD_HEIGHT // 2)

    boxes = []
    for i, (letter, name) in enumerate(options):
        boxX = panelRect.left + gap + i * (boxSize + gap)
        boxY = panelRect.top + titleHeight
        boxes.append((p.Rect(boxX, boxY, boxSize, boxSize), letter, name))

    # dim the board behind the panel so it's still visible but clearly not interactive
    dimOverlay = p.Surface((BOARD_WIDTH, BOARD_HEIGHT))
    dimOverlay.set_alpha(120)
    dimOverlay.fill(p.Color("black"))

    titleSurf = titleFont.render("Choose your promotion", True, p.Color("white"))

    choice = None
    choosing = True
    while choosing:
        mousePos = p.mouse.get_pos()

        screen.blit(dimOverlay, (0, 0))
        p.draw.rect(screen, p.Color(30, 30, 30), panelRect, border_radius=10)
        p.draw.rect(screen, p.Color("gold"), panelRect, 2, border_radius=10)

        titleLocation = titleSurf.get_rect(centerx=panelRect.centerx, top=panelRect.top + 8)
        screen.blit(titleSurf, titleLocation)

        for rect, letter, name in boxes:
            hovered = rect.collidepoint(mousePos)
            bgColor = p.Color("gold") if hovered else p.Color("white")
            p.draw.rect(screen, bgColor, rect)
            p.draw.rect(screen, p.Color("black"), rect, 2)
            screen.blit(IMAGES[color + letter], rect)

            labelColor = p.Color("gold") if hovered else p.Color("white")
            labelSurf = labelFont.render(name, True, labelColor)
            labelLocation = labelSurf.get_rect(centerx=rect.centerx, top=rect.bottom + 4)
            screen.blit(labelSurf, labelLocation)

        p.display.flip()

        for e in p.event.get():
            if e.type == p.QUIT:
                p.quit()
                exit()
            elif e.type == p.MOUSEBUTTONDOWN:
                for rect, letter, name in boxes:
                    if rect.collidepoint(mousePos):
                        choice = letter
                        choosing = False
            elif e.type == p.KEYDOWN:
                keyToLetter = {p.K_q: 'Q', p.K_r: 'R', p.K_b: 'B', p.K_n: 'N'}
                if e.key in keyToLetter:
                    choice = keyToLetter[e.key]
                    choosing = False

    return choice

def drawEndGameText(screen, text):
    font = p.font.SysFont("Helvetica", 32, True, False)
    textObject = font.render(text, 0, p.Color('Gray'))
    textLocation = p.Rect(0, 0, BOARD_WIDTH, BOARD_HEIGHT).move(BOARD_WIDTH/2 - textObject.get_width()/2, BOARD_HEIGHT/2 - textObject.get_height()/2) # centering the text
    screen.blit(textObject, textLocation)
    textObject = font.render(text, 0, p.Color('Black'))
    screen.blit(textObject, textLocation.move(2, 2))

if __name__ == "__main__":
    main()