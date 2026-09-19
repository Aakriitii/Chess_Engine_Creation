import random


class ChessAI:
    """
    Encapsulates move selection for the AI: material/positional scoring
    tables and a negamax + alpha-beta search. Search state (nextMove,
    counter) lives on the instance instead of module-level globals, so
    each ChessAI has its own isolated search state.
    """

    CHECKMATE = 1000
    STALEMATE = 0
    INFINITY = float("inf")  # search window bounds; wider than any score so mate-distance bonuses fit inside
    DEFAULT_DEPTH = 2

    pieceScore = {"K": 0, "Q": 10, "R": 5, "B": 3, "N": 3, "p": 1}

    knightScores = [[1, 1, 1, 1, 1, 1, 1, 1],
                    [1, 2, 2, 2, 2, 2, 2, 1],
                    [1, 2, 3, 3, 3, 3, 2, 1],
                    [1, 2, 3, 4, 4, 3, 2, 1],
                    [1, 2, 3, 4, 4, 3, 2, 1],
                    [1, 2, 3, 3, 3, 3, 2, 1],
                    [1, 2, 2, 2, 2, 2, 2, 1],
                    [1, 1, 1, 1, 1, 1, 1, 1]]

    bishopScores = [[4, 3, 2, 1, 1, 2, 3, 4],
                    [3, 4, 3, 2, 2, 3, 4, 3],
                    [2, 3, 4, 3, 3, 4, 3, 2],
                    [1, 2, 3, 4, 4, 3, 2, 1],
                    [1, 2, 3, 4, 4, 3, 2, 1],
                    [2, 3, 4, 3, 3, 4, 3, 2],
                    [3, 4, 3, 2, 2, 3, 4, 3],
                    [4, 3, 2, 1, 1, 2, 3, 4]]

    queenScores = [[1, 1, 1, 3, 1, 1, 1, 1],
                   [1, 2, 3, 3, 3, 1, 1, 1],
                   [1, 4, 3, 3, 3, 4, 2, 1],
                   [1, 2, 3, 3, 3, 2, 2, 1],
                   [1, 2, 3, 3, 3, 2, 2, 1],
                   [1, 4, 3, 3, 3, 4, 2, 1],
                   [1, 1, 2, 3, 3, 1, 1, 1],
                   [1, 1, 1, 3, 1, 1, 1, 1]]

    rookScores = [[4, 3, 4, 4, 4, 4, 3, 4],
                  [4, 4, 4, 4, 4, 4, 4, 4],
                  [1, 1, 2, 3, 3, 2, 1, 1],
                  [1, 2, 3, 4, 4, 3, 2, 1],
                  [1, 2, 3, 4, 4, 3, 2, 1],
                  [1, 1, 2, 2, 2, 2, 1, 1],
                  [4, 4, 4, 4, 4, 4, 4, 4],
                  [4, 3, 4, 4, 4, 4, 3, 4]]

    whitePawnScores = [[8, 8, 8, 8, 8, 8, 8, 8],
                       [8, 8, 8, 8, 8, 8, 8, 8],
                       [5, 6, 6, 7, 7, 6, 6, 5],
                       [2, 3, 3, 5, 5, 3, 3, 2],
                       [1, 2, 3, 4, 4, 3, 2, 1],
                       [1, 1, 2, 3, 3, 2, 1, 1],
                       [1, 1, 1, 0, 0, 1, 1, 1],
                       [0, 0, 0, 0, 0, 0, 0, 0]]

    blackPawnScores = [[0, 0, 0, 0, 0, 0, 0, 0],
                       [1, 1, 1, 0, 0, 1, 1, 1],
                       [1, 1, 2, 3, 3, 2, 1, 1],
                       [1, 2, 3, 4, 4, 3, 2, 1],
                       [2, 3, 3, 5, 5, 3, 3, 2],
                       [5, 6, 6, 7, 7, 6, 6, 5],
                       [8, 8, 8, 8, 8, 8, 8, 8],
                       [8, 8, 8, 8, 8, 8, 8, 8]]

    def __init__(self, depth=None):
        """
        depth: how many plies the search looks ahead. Higher = stronger
        but slower play. Defaults to DEFAULT_DEPTH (2, "medium") if not given.
        Roughly: 1 = easy, 2 = medium, 3 = hard.
        """
        self.piecePositionScores = {
            "N": self.knightScores, "Q": self.queenScores, "B": self.bishopScores,
            "R": self.rookScores, "bp": self.blackPawnScores, "wp": self.whitePawnScores
        }
        self.depth = depth if depth is not None else self.DEFAULT_DEPTH
        self.nextMove = None
        self.counter = 0

    @staticmethod
    def findRandomMove(validMoves):
        """Picks and returns a random move."""
        if not validMoves:
            return None
        return random.choice(validMoves)

    def findBestMove(self, gs, validMoves, returnQueue):
        """
        Entry point meant to be run in its own process (see ChessMain's
        runAIMove). Puts the chosen move on returnQueue once the search
        completes.
        """
        self.nextMove = None
        self.counter = 0
        self.findMoveNegaMaxAlphaBeta(gs, validMoves, self.depth, -self.INFINITY, self.INFINITY,
                                       1 if gs.whiteToMove else -1)
        print(self.counter)
        returnQueue.put(self.nextMove)

    def findMoveMinMax(self, gs, validMoves, depth, whiteToMove):
        """
        MinMax search based on material and depth of moves. Kept for
        reference/experimentation; findBestMove uses the faster
        alpha-beta version below.
        """
        if depth == 0:
            return self.scoreMaterial(gs.board)

        if whiteToMove:
            maxScore = -self.CHECKMATE
            for move in validMoves:
                gs.makeMove(move)
                nextMoves = gs.getValidMoves()
                score = self.findMoveMinMax(gs, nextMoves, depth - 1, False)
                if score > maxScore:
                    maxScore = score
                    if depth == self.depth:
                        self.nextMove = move
                gs.undoMove()
            return maxScore
        else:
            minScore = self.CHECKMATE
            for move in validMoves:
                gs.makeMove(move)
                nextMoves = gs.getValidMoves()
                score = self.findMoveMinMax(gs, nextMoves, depth - 1, True)
                if score < minScore:
                    minScore = score
                    if depth == self.depth:
                        self.nextMove = move
                gs.undoMove()
            return minScore

    def findMoveNegaMax(self, gs, validMoves, depth, turnMultiplier):
        """Negamax without pruning. Kept for reference; see the alpha-beta version below."""
        self.counter += 1
        if depth == 0 or not validMoves:
            return turnMultiplier * self.leafScore(gs, depth)

        maxScore = -self.INFINITY
        for move in validMoves:
            gs.makeMove(move)
            nextMoves = gs.getValidMoves()
            score = -self.findMoveNegaMax(gs, nextMoves, depth - 1, -turnMultiplier)
            if score > maxScore:
                maxScore = score
                if depth == self.depth:
                    self.nextMove = move
            gs.undoMove()
        return maxScore

    def findMoveNegaMaxAlphaBeta(self, gs, validMoves, depth, alpha, beta, turnMultiplier):
        """
        alpha = upper bound of the best score for the maximizing player
        beta = lower bound of the best score for the minimizing player
        """
        self.counter += 1
        # also stop when there are no legal moves: that is checkmate or stalemate reached with depth to spare.
        # Without this the empty loop below returned -CHECKMATE for stalemate too, so the AI saw
        # stalemating its opponent as a win.
        if depth == 0 or not validMoves:
            return turnMultiplier * self.leafScore(gs, depth)

        # move ordering - implement later
        maxScore = -self.INFINITY  # not -CHECKMATE: a position where every move loses would otherwise never set nextMove
        for move in validMoves:
            gs.makeMove(move)
            nextMoves = gs.getValidMoves()
            score = -self.findMoveNegaMaxAlphaBeta(gs, nextMoves, depth - 1, -beta, -alpha, -turnMultiplier)
            if score > maxScore:
                maxScore = score
                if depth == self.depth:
                    self.nextMove = move
            gs.undoMove()
            if maxScore > alpha:  # pruning happens, cutting off branches
                alpha = maxScore
            if alpha >= beta:
                break
        return maxScore

    def leafScore(self, gs, depth):
        """
        scoreBoard for a search leaf. depth is the search depth still remaining at the leaf, so a checkmate
        found higher up the tree (more depth left) scores slightly better than a slower one: the AI takes
        the quickest mate instead of a later one that scores the same.
        """
        score = self.scoreBoard(gs)
        if score >= self.CHECKMATE:
            score += depth
        elif score <= -self.CHECKMATE:
            score -= depth
        return score

    def scoreBoard(self, gs):
        """A positive score is good for white, a negative score is good for black."""
        if gs.checkMate:
            return -self.CHECKMATE if gs.whiteToMove else self.CHECKMATE
        elif gs.staleMate:
            return self.STALEMATE

        score = 0
        for row in range(len(gs.board)):
            for col in range(len(gs.board[row])):
                square = gs.board[row][col]
                if square != "--":
                    piecePositionScore = 0
                    if square[1] != "K":  # no position table for king
                        if square[1] == "p":  # for pawns
                            piecePositionScore = self.piecePositionScores[square][row][col]
                        else:  # for other pieces
                            piecePositionScore = self.piecePositionScores[square[1]][row][col]

                    if square[0] == 'w':
                        score += self.pieceScore[square[1]] + piecePositionScore * .1
                    elif square[0] == 'b':
                        score -= self.pieceScore[square[1]] + piecePositionScore * .1

        return score

    @classmethod
    def scoreMaterial(cls, board):
        """Score the board based on material alone."""
        score = 0
        for row in board:
            for square in row:
                if square[0] == 'w':
                    score += cls.pieceScore[square[1]]
                elif square[0] == 'b':
                    score -= cls.pieceScore[square[1]]
        return score