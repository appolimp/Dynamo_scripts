import logging

from base.wrapper import DB, doc
from math import pi
from .my_geom import MyPoints


def calc_angle_to_ver_or_hor_side(main_vector, second_vector):
    """
    Calc angle between main and second

    Then transform it to main vector or it perpendicular and make angle less than 90

    :param main_vector: DB.XYZ
    :param second_vector: DB.XYZ, for example UpDirection of view
    :return: Angle between main and second < 90
    :rtype: float
    """

    angle = main_vector.AngleTo(second_vector)
    logging.debug('Calc first rotation angle: {:.2f}'.format(angle * 180 / pi))

    if pi / 4 < angle <= pi / 2:
        angle -= pi / 2
    elif pi / 2 < angle <= 3 * pi / 4:
        angle += pi / 2 - pi
    elif 3 * pi / 4 < angle <= pi:
        angle -= pi

    logging.debug('Calc change rotation angle: {:.2f}'.format(angle * 180 / pi))
    sign_angle = MyPoints.calc_sign(main_vector, second_vector) * angle

    logging.debug('Calc sign rotation angle: {:.2f}'.format(sign_angle * 180 / pi))
    return sign_angle


def get_depends_elems_id_by_class(view, cur_class):
    my_filter = DB.ElementClassFilter(cur_class)
    elems_ids = view.GetDependentElements(my_filter)

    logging.debug('View #{}. Get {} id elems by class: {}'.format(view.Id, len(elems_ids), cur_class))
    return elems_ids


def get_depends_elems_by_class(view, cur_class):
    elems_ids = get_depends_elems_id_by_class(view, cur_class)
    elems = get_elems_by_ids(elems_ids)

    logging.debug('View #{}. Get {} elems by class: {}'.format(view.Id, len(elems), cur_class))
    return elems


def get_elems_by_ids(list_ids):
    elems = []

    for elem_id in list_ids:
        elem = doc.GetElement(elem_id)
        if elem is not None:
            elems.append(elem)

    return elems
