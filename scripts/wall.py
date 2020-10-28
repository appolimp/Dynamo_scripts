# coding=utf-8
from base.wrapper import transaction, doc, DB, UnwrapElement
from base.exeption import ScriptError
import logging


def main():
    WALLS = UnwrapElement(IN[0])
    START = IN[1]
    END = IN[2]
    change_wall_join(WALLS, START, END)


def change_wall_join(walls, start=True, end=True):

    for wall in walls:
        set_wall_join(wall, side=0, join=start)
        set_wall_join(wall, side=1, join=end)


@transaction
def set_wall_join(wall, side=1, join=True):
    if DB.WallUtils.IsWallJoinAllowedAtEnd(wall, side) is not join:
        if join is True:
            DB.WallUtils.AllowWallJoinAtEnd(wall, side)
        else:
            DB.WallUtils.DisallowWallJoinAtEnd(wall, side)


if __name__ == '__main__':
    logging.basicConfig(
        filename=None, level=logging.INFO,
        format='[%(asctime)s] %(levelname).1s <example>: %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S')

    try:
        main()
    except ScriptError as e:
        logging.error(e)
    except Exception as err:
        logging.exception('Critical error')
