"""
Main driver: a ChessGame class responsible for handling user input and
displaying the current GameState object.
"""

import pygame as p
import ChessEngine
from SmartMoveFinder import ChessAI
from multiprocessing import Process, Queue
import queue

class ChessGame:
    BOARD_WIDTH = BOARD_HEIGHT = 512  # 400 is another option
    MOVE_LOG_PANEL_WIDTH = 250
    MOVE_LOG_PANEL_HEIGHT = BOARD_HEIGHT
    DIMENSION = 8  # dimensions of a chess board are 8 x 8
    SQ_SIZE = BOARD_HEIGHT // DIMENSION
    MAX_FPS = 15  # for animations later on
    PIECE_NAMES = ['wp', 'wR', 'wN', 'wB', 'wK', 'wQ', 'bp', 'bR', 'bN', 'bB', 'bK', 'bQ']

    # Board (back to the original black & white look)
    LIGHT_SQUARE_COLOR = (255, 255, 255)   # white
    DARK_SQUARE_COLOR = (190, 190, 190)    # gray

    # In-game highlights (original blue/yellow, kept as-is)
    SELECTED_COLOR = (0, 0, 255)           # blue - square clicked
    MOVE_HINT_COLOR = (255, 255, 0)        # yellow - legal destinations
    CHECK_COLOR = (235, 149, 64)           # amber - king in check (no red)
    CHECK_BANNER_COLOR = (196, 120, 45)    # deeper amber - status banner bg

    # Panels / menus (game mode, difficulty, promotion popups) - original black & white + gold accent
    MENU_BG_COLOR = (0, 0, 0)              # black backdrop
    PANEL_BG_COLOR = (40, 40, 40)          # panel/button fill
    PANEL_HOVER_COLOR = (70, 70, 70)       # button hover fill
    ACCENT_COLOR = (255, 215, 0)           # gold - borders, hover accents

    # Text
    TEXT_PRIMARY_COLOR = (255, 255, 255)   # white
    TEXT_MUTED_COLOR = (190, 190, 190)     # gray for descriptions

    # Move log
    MOVE_LOG_BG_COLOR = (0, 0, 0)          # black

    def __init__(self, playerOne=None, playerTwo=None, depth=None):
        """
        playerOne / playerTwo: True if a human is playing that side,
        False if the AI controls it. If either is left as None, the
        player is prompted with an on-screen menu (One Player / Two
        Players / Computer vs Computer) to choose before the game starts.

        depth: how many plies deep the AI searches (1=Easy, 2=Medium,
        3=Hard). If left as None and an AI is actually going to play
        (One Player or Computer vs Computer), the player is prompted
        with an on-screen difficulty menu. In Two Players mode there's
        no AI turn to take, so the prompt is skipped.
        """
        p.init()
        self.screen = p.display.set_mode((self.BOARD_WIDTH + self.MOVE_LOG_PANEL_WIDTH, self.BOARD_HEIGHT))
        self.clock = p.time.Clock()
        self.screen.fill(p.Color(*self.MENU_BG_COLOR))
        self.moveLogFont = p.font.SysFont("Arial", 14, False, False)
        self.colors = [p.Color(*self.LIGHT_SQUARE_COLOR), p.Color(*self.DARK_SQUARE_COLOR)]

        self.images = {}
        self.loadImages()  # only do this once, before the game loop

        if playerOne is None or playerTwo is None:
            playerOne, playerTwo = self.selectGameMode()

        aiIsPlaying = not (playerOne and playerTwo)
        if depth is None and aiIsPlaying:
            depth = self.selectDifficulty()

        self.gs = ChessEngine.GameState()
        self.ai = ChessAI(depth=depth)
        self.validMoves = self.gs.getValidMoves()
        print(self.gs.board)

        self.running = True
        self.moveMade = False  # flag for when a move is made
        self.animate = False  # flag for when we should animate a move
        self.sqSelected = ()  # no square selected; last click of the user (tuple: (row, col))
        self.playerClicks = []  # keeps track of player clicks (two tuples: [(6, 4), (4, 4)])
        self.gameOver = False
        self.playerOne = playerOne  # if a human is playing white, this is True
        self.playerTwo = playerTwo  # same as above but for black
        self.humanTurn = True
        self.AIThinking = False
        self.moveFinderProcess = None
        self.returnQueue = None
        self.moveUndone = False

    def selectGameMode(self):
        """
        Blocks (with its own small event loop) until the player picks a
        game mode from an on-screen menu, then returns (playerOne, playerTwo):
          - One Player:            human plays White vs the AI (True, False)
          - Two Players:            human vs human, both sides (True, True)
          - Computer vs Computer:  AI plays both sides (False, False)
        """
        titleFont = p.font.SysFont("Arial", 30, True, False)
        optionFont = p.font.SysFont("Arial", 20, True, False)
        descFont = p.font.SysFont("Arial", 14, False, False)

        options = [
            ("One Player", "You play White against the computer", True, False),
            ("Two Players", "Play against a friend on this device", True, True),
            ("Computer vs Computer", "Watch the AI play against itself", False, False),
        ]

        screenWidth = self.BOARD_WIDTH + self.MOVE_LOG_PANEL_WIDTH
        screenHeight = self.BOARD_HEIGHT

        buttonWidth = 380
        buttonHeight = 74
        gap = 22
        startY = 170

        buttons = []
        for i, (label, desc, p1, p2) in enumerate(options):
            rect = p.Rect((screenWidth - buttonWidth) // 2, startY + i * (buttonHeight + gap),
                           buttonWidth, buttonHeight)
            buttons.append((rect, label, desc, p1, p2))

        titleSurf = titleFont.render("Choose Game Mode", True, p.Color(*self.TEXT_PRIMARY_COLOR))

        result = None
        choosing = True
        while choosing:
            mousePos = p.mouse.get_pos()
            self.screen.fill(p.Color(*self.MENU_BG_COLOR))

            titleLocation = titleSurf.get_rect(centerx=screenWidth // 2, top=70)
            self.screen.blit(titleSurf, titleLocation)

            for rect, label, desc, p1, p2 in buttons:
                hovered = rect.collidepoint(mousePos)
                bgColor = p.Color(*self.PANEL_HOVER_COLOR) if hovered else p.Color(*self.PANEL_BG_COLOR)
                borderColor = p.Color(*self.ACCENT_COLOR) if hovered else p.Color(*self.TEXT_MUTED_COLOR)
                p.draw.rect(self.screen, bgColor, rect, border_radius=10)
                p.draw.rect(self.screen, borderColor, rect, 2, border_radius=10)

                labelSurf = optionFont.render(label, True, p.Color(*self.TEXT_PRIMARY_COLOR))
                labelLocation = labelSurf.get_rect(centerx=rect.centerx, top=rect.top + 10)
                self.screen.blit(labelSurf, labelLocation)

                descSurf = descFont.render(desc, True, p.Color(*self.TEXT_MUTED_COLOR))
                descLocation = descSurf.get_rect(centerx=rect.centerx, top=rect.top + 40)
                self.screen.blit(descSurf, descLocation)

            p.display.flip()

            for e in p.event.get():
                if e.type == p.QUIT:
                    p.quit()
                    exit()
                elif e.type == p.MOUSEBUTTONDOWN:
                    for rect, label, desc, p1, p2 in buttons:
                        if rect.collidepoint(mousePos):
                            result = (p1, p2)
                            choosing = False

            self.clock.tick(self.MAX_FPS)

        return result

    def selectDifficulty(self):
        """
        Blocks (with its own small event loop) until the player picks a
        difficulty from an on-screen menu, then returns the corresponding
        search depth: Easy=1, Medium=2, Hard=3. Only called when an AI is
        actually going to play (see __init__).
        """
        titleFont = p.font.SysFont("Arial", 30, True, False)
        optionFont = p.font.SysFont("Arial", 20, True, False)
        descFont = p.font.SysFont("Arial", 14, False, False)

        options = [
            ("Easy", "Depth 1 - fast, plays casually", 1),
            ("Medium", "Depth 2 - a balanced challenge", 2),
            ("Hard", "Depth 3 - slower moves, plays tougher", 3),
        ]

        screenWidth = self.BOARD_WIDTH + self.MOVE_LOG_PANEL_WIDTH
        screenHeight = self.BOARD_HEIGHT

        buttonWidth = 380
        buttonHeight = 74
        gap = 22
        startY = 170

        buttons = []
        for i, (label, desc, depthValue) in enumerate(options):
            rect = p.Rect((screenWidth - buttonWidth) // 2, startY + i * (buttonHeight + gap),
                           buttonWidth, buttonHeight)
            buttons.append((rect, label, desc, depthValue))

        titleSurf = titleFont.render("Choose Difficulty", True, p.Color(*self.TEXT_PRIMARY_COLOR))

        result = None
        choosing = True
        while choosing:
            mousePos = p.mouse.get_pos()
            self.screen.fill(p.Color(*self.MENU_BG_COLOR))

            titleLocation = titleSurf.get_rect(centerx=screenWidth // 2, top=70)
            self.screen.blit(titleSurf, titleLocation)

            for rect, label, desc, depthValue in buttons:
                hovered = rect.collidepoint(mousePos)
                bgColor = p.Color(*self.PANEL_HOVER_COLOR) if hovered else p.Color(*self.PANEL_BG_COLOR)
                borderColor = p.Color(*self.ACCENT_COLOR) if hovered else p.Color(*self.TEXT_MUTED_COLOR)
                p.draw.rect(self.screen, bgColor, rect, border_radius=10)
                p.draw.rect(self.screen, borderColor, rect, 2, border_radius=10)

                labelSurf = optionFont.render(label, True, p.Color(*self.TEXT_PRIMARY_COLOR))
                labelLocation = labelSurf.get_rect(centerx=rect.centerx, top=rect.top + 10)
                self.screen.blit(labelSurf, labelLocation)

                descSurf = descFont.render(desc, True, p.Color(*self.TEXT_MUTED_COLOR))
                descLocation = descSurf.get_rect(centerx=rect.centerx, top=rect.top + 40)
                self.screen.blit(descSurf, descLocation)

            p.display.flip()

            for e in p.event.get():
                if e.type == p.QUIT:
                    p.quit()
                    exit()
                elif e.type == p.MOUSEBUTTONDOWN:
                    for rect, label, desc, depthValue in buttons:
                        if rect.collidepoint(mousePos):
                            result = depthValue
                            choosing = False

            self.clock.tick(self.MAX_FPS)

        return result

    def loadImages(self):
        """Initialize the dictionary of piece images. Called exactly once, before the game loop."""
        for piece in self.PIECE_NAMES:
            self.images[piece] = p.transform.scale(
                p.image.load("images/" + piece + ".png"), (self.SQ_SIZE, self.SQ_SIZE))
        # Note: an image can be accessed with self.images['wp']

    def run(self):
        """The main game loop: handles input, updates the game state, and draws the graphics."""
        while self.running:
            self.humanTurn = (self.gs.whiteToMove and self.playerOne) or \
                              (not self.gs.whiteToMove and self.playerTwo)
            self.handleEvents()

            # AI move finder (MinMax / alpha-beta algorithm)
            if not self.gameOver and not self.humanTurn and not self.moveUndone:
                self.driveAIMove()

            if self.moveMade:
                if self.animate:
                    self.animateMove(self.gs.moveLog[-1])
                self.validMoves = self.gs.getValidMoves()
                self.moveMade = False
                self.animate = False
                self.moveUndone = False

            self.drawGameState()

            if self.gs.checkMate or self.gs.staleMate:
                self.gameOver = True
                if self.gs.staleMate:
                    text = 'Stalemate'
                else:
                    text = 'Black Wins by Checkmate!' if self.gs.whiteToMove else 'White wins by CheckMate!'
                self.drawEndGameText(text)

            self.clock.tick(self.MAX_FPS)
            p.display.flip()

    def handleEvents(self):
        for e in p.event.get():
            if e.type == p.QUIT:
                self.running = False
            elif e.type == p.MOUSEBUTTONDOWN:
                self.handleMouseClick()
            elif e.type == p.KEYDOWN:
                self.handleKeyDown(e.key)

    def handleMouseClick(self):
        if self.gameOver:
            return
        location = p.mouse.get_pos()  # (x, y) location of mouse
        col = location[0] // self.SQ_SIZE
        row = location[1] // self.SQ_SIZE
        if self.sqSelected == (row, col) or col >= 8:  # same square clicked twice, or clicked the move log
            self.sqSelected = ()  # deselect
            self.playerClicks = []  # clear player clicks
        else:
            self.sqSelected = (row, col)
            self.playerClicks.append(self.sqSelected)  # append for both 1st and 2nd clicks

        if len(self.playerClicks) == 2 and self.humanTurn:  # after 2nd click
            move = ChessEngine.Move(self.playerClicks[0], self.playerClicks[1], self.gs.board)
            print(move.getChessNotation())

            moveFound = False
            for validMove in self.validMoves:
                if move == validMove:
                    if validMove.pawnPromotion:
                        validMove.promotionChoice = self.getPromotionChoice(self.gs.whiteToMove)
                    self.gs.makeMove(validMove)
                    self.moveMade = True
                    moveFound = True
                    self.animate = True
                    self.sqSelected = ()  # reset user clicks
                    self.playerClicks = []
                    break
            if not moveFound:
                self.playerClicks = [self.sqSelected]

    def handleKeyDown(self, key):
        if key == p.K_z:  # undo when 'z' is pressed
            self.gs.undoMove()
            self.moveMade = True
            self.animate = False
            self.gameOver = False
            self.stopAIThinking()
            self.moveUndone = True
        if key == p.K_r:  # reset the game when 'r' is pressed
            self.gs = ChessEngine.GameState()
            self.validMoves = self.gs.getValidMoves()
            self.sqSelected = ()
            self.playerClicks = []
            self.moveMade = False
            self.animate = False
            self.gameOver = False
            self.stopAIThinking()
            self.moveUndone = True

    def stopAIThinking(self):
        if self.AIThinking:
            self.moveFinderProcess.terminate()
            self.AIThinking = False

    def driveAIMove(self):
        """Kicks off (and later collects the result of) the AI's search, run in a separate process."""
        if not self.AIThinking:
            self.AIThinking = True
            print("Thinking...")
            self.returnQueue = Queue()  # used to pass data between processes
            self.moveFinderProcess = Process(target=self.ai.findBestMove,
                                              args=(self.gs, self.validMoves, self.returnQueue))
            self.moveFinderProcess.start()

        if not self.moveFinderProcess.is_alive():
            print("Done thinking")
            try:
                AIMove = self.returnQueue.get(timeout=0.1)
            except queue.Empty:
                AIMove = None
            if AIMove is None:
                AIMove = ChessAI.findRandomMove(self.validMoves)
            self.gs.makeMove(AIMove)
            self.moveMade = True
            self.animate = True
            self.AIThinking = False

    def drawGameState(self):
        """Responsible for all the graphics within the current game state."""
        self.drawBoard()  # draw squares on the board
        self.highlightSquares()
        # add in piece highlighting or move suggestions (later)
        self.drawPieces()  # draw pieces on top of those squares
        self.drawMoveLog()

    def drawBoard(self):
        """Draw the squares on the board. The top-left square is always light."""
        for r in range(self.DIMENSION):
            for c in range(self.DIMENSION):
                color = self.colors[(r + c) % 2]
                p.draw.rect(self.screen, color, p.Rect(c * self.SQ_SIZE, r * self.SQ_SIZE,
                                                         self.SQ_SIZE, self.SQ_SIZE))

    def highlightSquares(self):
        """Highlights the square selected, valid moves from it, and the king if in check."""
        gs = self.gs

        # Highlight the king in check, regardless of what's currently selected
        if gs.inCheck and not (gs.checkMate or gs.staleMate):
            kingRow, kingCol = gs.whiteKingLocation if gs.whiteToMove else gs.blackKingLocation
            s = p.Surface((self.SQ_SIZE, self.SQ_SIZE))
            s.set_alpha(160)
            s.fill(p.Color(*self.CHECK_COLOR))
            self.screen.blit(s, (kingCol * self.SQ_SIZE, kingRow * self.SQ_SIZE))

        if self.sqSelected != ():
            r, c = self.sqSelected  # reference to row and column of the square selected
            if gs.board[r][c][0] == ('w' if gs.whiteToMove else 'b'):  # sqSelected is a piece that can move
                # highlight selected square
                s = p.Surface((self.SQ_SIZE, self.SQ_SIZE))
                s.set_alpha(120)  # transparency value -> 0 transparent; 255 opaque
                s.fill(p.Color(*self.SELECTED_COLOR))
                self.screen.blit(s, (c * self.SQ_SIZE, r * self.SQ_SIZE))
                # highlight moves from that square
                s.fill(p.Color(*self.MOVE_HINT_COLOR))
                for move in self.validMoves:
                    if move.startRow == r and move.startCol == c:
                        self.screen.blit(s, (self.SQ_SIZE * move.endCol, move.endRow * self.SQ_SIZE))

    def drawPieces(self):
        """Draw the pieces on the board using the current GameState.board."""
        board = self.gs.board
        for r in range(self.DIMENSION):
            for c in range(self.DIMENSION):
                piece = board[r][c]
                if piece != "--":  # not empty square
                    self.screen.blit(self.images[piece], p.Rect(c * self.SQ_SIZE, r * self.SQ_SIZE,
                                                                  self.SQ_SIZE, self.SQ_SIZE))

    def drawMoveLog(self):
        """Draws the move log, plus a status banner when the side to move is in check."""
        gs = self.gs
        moveLogRect = p.Rect(self.BOARD_WIDTH, 0, self.MOVE_LOG_PANEL_WIDTH, self.MOVE_LOG_PANEL_HEIGHT)
        p.draw.rect(self.screen, p.Color(*self.MOVE_LOG_BG_COLOR), moveLogRect)
        moveLog = gs.moveLog
        moveTexts = []
        for i in range(0, len(moveLog), 2):
            moveString = str(i // 2 + 1) + ". " + str(moveLog[i]) + " "
            if i + 1 < len(moveLog):  # make sure black made a move
                moveString += str(moveLog[i + 1]) + "  "
            moveTexts.append(moveString)

        movesPerRow = 3
        padding = 5
        lineSpacing = 2
        textY = padding
        for i in range(0, len(moveTexts), movesPerRow):
            text = ""
            for j in range(movesPerRow):
                if i + j < len(moveTexts):
                    text += moveTexts[i + j]
            textObject = self.moveLogFont.render(text, True, p.Color(*self.TEXT_PRIMARY_COLOR))
            textLocation = moveLogRect.move(padding, textY)
            self.screen.blit(textObject, textLocation)
            textY += textObject.get_height() + lineSpacing

        # status banner: whose turn is in check, if any
        if gs.inCheck and not (gs.checkMate or gs.staleMate):
            bannerHeight = 36
            bannerRect = p.Rect(self.BOARD_WIDTH, self.MOVE_LOG_PANEL_HEIGHT - bannerHeight,
                                 self.MOVE_LOG_PANEL_WIDTH, bannerHeight)
            p.draw.rect(self.screen, p.Color(*self.CHECK_BANNER_COLOR), bannerRect)
            checkFont = p.font.SysFont("Arial", 20, True, False)
            who = "White" if gs.whiteToMove else "Black"
            checkSurf = checkFont.render(f"{who} is in CHECK!", True, p.Color(*self.TEXT_PRIMARY_COLOR))
            checkLocation = checkSurf.get_rect(center=bannerRect.center)
            self.screen.blit(checkSurf, checkLocation)

    def animateMove(self, move):
        """Animates a move."""
        dR = move.endRow - move.startRow
        dC = move.endCol - move.startCol
        framesPerSquare = 10  # frames to move one square
        frameCount = (abs(dR) + abs(dC)) * framesPerSquare
        board = self.gs.board
        for frame in range(frameCount + 1):
            r, c = (move.startRow + dR * frame / frameCount, move.startCol + dC * frame / frameCount)
            self.drawBoard()
            self.drawPieces()
            # erase the piece moved from its ending square
            color = self.colors[(move.endRow + move.endCol) % 2]
            endSquare = p.Rect(move.endCol * self.SQ_SIZE, move.endRow * self.SQ_SIZE, self.SQ_SIZE, self.SQ_SIZE)
            p.draw.rect(self.screen, color, endSquare)
            # draw captured piece onto rectangle
            if move.pieceCaptured != "--":
                if move.enPassant:
                    enPassantRow = move.endRow + 1 if move.pieceCaptured[0] == 'b' else move.endRow - 1
                    endSquare = p.Rect(move.endCol * self.SQ_SIZE, enPassantRow * self.SQ_SIZE,
                                        self.SQ_SIZE, self.SQ_SIZE)
                self.screen.blit(self.images[move.pieceCaptured], endSquare)
            # draw moving piece
            if move.pieceMoved != '--':
                self.screen.blit(self.images[move.pieceMoved], p.Rect(c * self.SQ_SIZE, r * self.SQ_SIZE,
                                                                        self.SQ_SIZE, self.SQ_SIZE))
            p.display.flip()
            self.clock.tick(60)

    def drawEndGameText(self, text):
        # dim the board so the result stands out, same treatment as the other popups
        overlay = p.Surface((self.BOARD_WIDTH, self.BOARD_HEIGHT))
        overlay.set_alpha(180)
        overlay.fill(p.Color(*self.MENU_BG_COLOR))
        self.screen.blit(overlay, (0, 0))

        font = p.font.SysFont("Helvetica", 32, True, False)
        textObject = font.render(text, True, p.Color(*self.TEXT_PRIMARY_COLOR))
        textLocation = textObject.get_rect(center=(self.BOARD_WIDTH // 2, self.BOARD_HEIGHT // 2))
        self.screen.blit(textObject, textLocation)

        # thin gold accent underline, ties it visually to the menus/popups
        underline = p.Rect(0, 0, textObject.get_width() + 40, 3)
        underline.center = (self.BOARD_WIDTH // 2, textLocation.bottom + 14)
        p.draw.rect(self.screen, p.Color(*self.ACCENT_COLOR), underline)

    def getPromotionChoice(self, whiteToMove):
        """
        Blocks (with its own small event loop) until the human clicks or types
        one of Q/R/B/N, then returns that letter. Only ever called for the
        human's own real move — the AI's simulated moves during search always
        keep Move's default 'Q'.
        """
        color = 'w' if whiteToMove else 'b'
        options = [('Q', 'Queen'), ('R', 'Rook'), ('B', 'Bishop'), ('N', 'Knight')]

        titleFont = p.font.SysFont("Arial", 22, True, False)
        labelFont = p.font.SysFont("Arial", 14, False, False)

        boxSize = self.SQ_SIZE
        gap = 16
        labelHeight = 22
        titleHeight = 40

        totalWidth = boxSize * len(options) + gap * (len(options) + 1)
        panelHeight = titleHeight + boxSize + labelHeight + gap * 2
        panelRect = p.Rect(0, 0, totalWidth, panelHeight)
        panelRect.center = (self.BOARD_WIDTH // 2, self.BOARD_HEIGHT // 2)

        boxes = []
        for i, (letter, name) in enumerate(options):
            boxX = panelRect.left + gap + i * (boxSize + gap)
            boxY = panelRect.top + titleHeight
            boxes.append((p.Rect(boxX, boxY, boxSize, boxSize), letter, name))

        # dim the board behind the panel so it's still visible but clearly not interactive
        dimOverlay = p.Surface((self.BOARD_WIDTH, self.BOARD_HEIGHT))
        dimOverlay.set_alpha(120)
        dimOverlay.fill(p.Color(*self.MENU_BG_COLOR))

        titleSurf = titleFont.render("Choose your promotion", True, p.Color(*self.TEXT_PRIMARY_COLOR))

        choice = None
        choosing = True
        while choosing:
            mousePos = p.mouse.get_pos()

            self.screen.blit(dimOverlay, (0, 0))
            p.draw.rect(self.screen, p.Color(*self.PANEL_BG_COLOR), panelRect, border_radius=10)
            p.draw.rect(self.screen, p.Color(*self.ACCENT_COLOR), panelRect, 2, border_radius=10)

            titleLocation = titleSurf.get_rect(centerx=panelRect.centerx, top=panelRect.top + 8)
            self.screen.blit(titleSurf, titleLocation)

            for rect, letter, name in boxes:
                hovered = rect.collidepoint(mousePos)
                bgColor = p.Color(*self.ACCENT_COLOR) if hovered else p.Color(*self.LIGHT_SQUARE_COLOR)
                p.draw.rect(self.screen, bgColor, rect)
                p.draw.rect(self.screen, p.Color(*self.MENU_BG_COLOR), rect, 2)
                self.screen.blit(self.images[color + letter], rect)

                labelColor = p.Color(*self.ACCENT_COLOR) if hovered else p.Color(*self.TEXT_PRIMARY_COLOR)
                labelSurf = labelFont.render(name, True, labelColor)
                labelLocation = labelSurf.get_rect(centerx=rect.centerx, top=rect.bottom + 4)
                self.screen.blit(labelSurf, labelLocation)

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


if __name__ == "__main__":
    game = ChessGame()
    game.run()