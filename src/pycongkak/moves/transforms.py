import copy
import itertools

import numpy as np

from pycongkak.board.constants import PITS_PER_SIDE
from pycongkak.board.containers import BoardState, Player, PlayerNumber
from pycongkak.board.transforms import active_player, opponent_player
from pycongkak.moves.containers import (
    BoardPerspective,
    MoveCase,
    MoveValidity,
)


def check_move_validity(
    board_state: BoardState,
    pit_number: int,
) -> MoveValidity:
    player = active_player(board_state)
    if (
        (player.side[pit_number] < 1)
        or (pit_number > PITS_PER_SIDE - 1)
        or (pit_number < 0)
    ):
        return MoveValidity.PIT
    else:
        return MoveValidity.VALID


def move(
    board_state: BoardState,
    pit_number: int,
) -> BoardState:
    selected_pit = pit_number
    move_valid = check_move_validity(board_state, pit_number)
    if move_valid != MoveValidity.VALID:
        raise ValueError("Invalid Move")
    player = copy.deepcopy(active_player(board_state))
    opponent = copy.deepcopy(opponent_player(board_state))

    initial_number = player.side[selected_pit]
    initial_score_mapping = {
        BoardPerspective.PLAYER: player.score,
        BoardPerspective.OPPONENT: opponent.score,
    }
    score = 0

    mapping: dict[BoardPerspective, Player] = {}
    board_sides = itertools.cycle(
        [
            (BoardPerspective.PLAYER, player.side),
            (BoardPerspective.OPPONENT, opponent.side),
        ]
    )

    # set selected pit = 0, taking marbles from this pit
    player.side[selected_pit] = 0
    mapping[BoardPerspective.PLAYER] = player
    mapping[BoardPerspective.OPPONENT] = opponent

    start_pit = selected_pit + 1
    spaces_to_end = PITS_PER_SIDE - start_pit
    overflow = initial_number - spaces_to_end

    while overflow > 0:
        side_enum, side_player = next(board_sides)
        if side_enum == BoardPerspective.PLAYER:
            score += 1
            overflow -= 1
        additional = np.zeros(PITS_PER_SIDE, dtype=np.int32)
        additional[start_pit:] = 1
        side_player += additional

        # resetting new values for loop
        start_pit = 0
        overflow -= PITS_PER_SIDE
        initial_number = PITS_PER_SIDE + overflow

        # saving data
        mapping[side_enum] = Player(
            number=mapping[side_enum].number,
            score=initial_score_mapping[side_enum],
            side=side_player,
        )

    # setting up next side of the board
    side_enum, side_player = next(board_sides)
    additional = np.zeros(PITS_PER_SIDE, dtype=np.int32)

    # this is the pit where last marble is dropped
    end_pit = start_pit + initial_number - 1
    end_pit_marbles = side_player[end_pit]

    # adding in marbles
    additional[start_pit : end_pit + 1] = 1
    side_player += additional

    mapping[side_enum] = Player(
        number=mapping[side_enum].number,
        score=initial_score_mapping[side_enum],
        side=side_player,
    )

    # adding scores from round
    for enum_n, player_n in mapping.items():
        if player_n.number == player.number:
            updated_player_n = add_score(score, player_n)
        else:
            updated_player_n = player_n
        mapping[enum_n] = updated_player_n

    # checking special conditions on turn end
    move_case = check_move_case(
        overflow=overflow, player_side=side_enum, end_pit_marbles=end_pit_marbles
    )
    # setting turn to appropriate
    turns_remaining = board_state.n_turns - 1
    extra_turns = 0
    # TODO: when I have 2 turns, I land in pit, I lose one of my free turns
    # TODO: Game should end when one player's side has 0 marbles remaining
    match move_case:
        case MoveCase.NORMAL:
            next_turn = (
                opponent.number
                if turns_remaining == 0
                else player.number
                if turns_remaining == 0
                else player.number
            )
            turns_remaining = 1
        case MoveCase.FREE:
            next_turn = player.number
            turns_remaining += 1
        case MoveCase.STEAL:
            next_turn = opponent.number if turns_remaining == 0 else player.number
            turns_remaining = 1
            mapping = steal(
                mapping=mapping,
                player_pit_number=end_pit,
            )
        case MoveCase.MISS:
            next_turn = opponent.number
            turns_remaining = 1
            extra_turns = 1

    # check if opponent's side on next move is empty
    if np.count_nonzero(mapping[BoardPerspective.OPPONENT].side) == 0:
        next_turn = player.number

    # updating player information
    if player.number == PlayerNumber.ONE:
        player_one = mapping[BoardPerspective.PLAYER]
        player_two = mapping[BoardPerspective.OPPONENT]
    else:
        player_one = mapping[BoardPerspective.OPPONENT]
        player_two = mapping[BoardPerspective.PLAYER]
    return BoardState(
        active=True,
        turn=next_turn,
        n_turns=turns_remaining + extra_turns,
        player_one=player_one,
        player_two=player_two,
    )


def add_score(
    score: int,
    player: Player,
) -> Player:
    return Player(number=player.number, score=player.score + score, side=player.side)


def check_move_case(
    overflow: int, player_side: BoardPerspective, end_pit_marbles: int
) -> MoveCase:
    # free condition: turn ends exactly before start of opponents pit (score pit)
    if (overflow == -PITS_PER_SIDE) and (player_side == BoardPerspective.OPPONENT):
        return MoveCase.FREE
    # steal condition: turn ends on empty pit, player side
    if (end_pit_marbles == 0) and (player_side == BoardPerspective.PLAYER):
        return MoveCase.STEAL
    # miss condition: turn ends on empty pit, opponent side
    if (end_pit_marbles == 0) and (player_side == BoardPerspective.OPPONENT):
        return MoveCase.MISS
    else:
        return MoveCase.NORMAL


def steal(
    mapping: dict[BoardPerspective, Player],
    player_pit_number: int,
) -> dict[BoardPerspective, Player]:
    player = mapping[BoardPerspective.PLAYER]
    opponent = mapping[BoardPerspective.OPPONENT]
    opponent_pit_number = PITS_PER_SIDE - 1 - player_pit_number
    stolen_marbles = opponent.side[opponent_pit_number]
    opponent.side[opponent_pit_number] = 0

    mapping[BoardPerspective.PLAYER] = Player(
        number=player.number, score=player.score + stolen_marbles, side=player.side
    )
    mapping[BoardPerspective.OPPONENT] = Player(
        number=opponent.number, score=opponent.score, side=opponent.side
    )
    return mapping
