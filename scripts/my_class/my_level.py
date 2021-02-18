from base.wrapper import DB, app, doc
from base.exeption import ElemNotFound
import logging


class Levels(object):
    instance = None

    def __new__(cls, *args, **kwargs):
        if Levels.instance is None:
            Levels.instance = object.__new__(Levels)
            logging.debug('Create Levels set')

        return Levels.instance

    def __init__(self):
        self._range_level = []
        self._create_range_level()

    def _create_range_level(self):
        collector = DB.FilteredElementCollector(doc).OfClass(DB.Level).ToElements()
        self._range_level = sorted([MyLevel(level) for level in collector])
        logging.debug('Fill level list for {} levels'.format(len(self._range_level)))

    @property
    def as_list(self):
        if not self._range_level:
            self._create_range_level()

        return self._range_level

    def get_level_by_point(self, point):
        """

        :param point:
        :type point:
        :return:
        :rtype: MyLevel
        """

        prev = self._range_level[0]

        for level in self._range_level:
            if level.elev > point.Z:
                if level is prev:
                    logging.error('Point under first level. Point height {:.3f} m'.format(point.Z * 0.3048))
                break

            prev = level
        else:
            logging.error('Point above upper level. Point height {:.3f} m'.format(point.Z * 0.3048))

        logging.debug('Current level is {}'.format(prev.level.Name))
        return prev

    def get_next(self, current_level):
        """

        :param current_level:
        :type current_level: MyLevel
        :return:
        :rtype: MyLevel
        """

        upper = self._range_level[-1]
        if upper is current_level:
            raise ElemNotFound('Level #{}. Next level not found. Last elevation is {:.2f} m'.format(
                current_level.level.Id, current_level.elev * 0.3048))

        for level in self._range_level[::-1]:
            if level is current_level:
                return upper

            upper = level

    def get_height_level_by_point(self, point):
        """

        :param point:
        :type point:
        :return:
        :rtype: float
        """

        cur_level = self.get_level_by_point(point)

        if cur_level.height is None:
            next_level = self.get_next(cur_level)
            cur_level.height = next_level.elev - cur_level.elev
            logging.debug('Level #{}. Calc height level: {:.3f}'.format(cur_level.level.Id, cur_level.height * 0.3048))

        return cur_level.height


class MyLevel:
    def __init__(self, level):
        self.level = level
        self.height = None
        self.elev = level.Elevation

    def __str__(self):
        return 'Level #{} "{}" at height {:.2f} m'.format(self.level.Id, self.level.Name, self.elev * 0.3048)

    def __lt__(self, other):
        return self.elev < other.elev

    def __eq__(self, other):
        return self.elev == other.elev

    def __ne__(self, other):
        return self.elev != other.elev

    def __gt__(self, other):
        return self.elev > other.elev
