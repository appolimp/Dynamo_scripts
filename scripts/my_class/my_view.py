# coding=utf-8
from base.wrapper import DB, doc, one_transaction_in_group
from math import pi

import logging
from . import my_features
from base import exeption as ex


class MyView:
    """
    My view class with features:

    - crop view by CurveLoop
    - rotate view about z axis by point and angle
    - create callout
    """

    def __init__(self, view):
        """
        Initialization of instance

        :param view: DB.View
        """

        self.view = view

    @classmethod
    def create_callout(cls, view_id, view_type_id, first_point=DB.XYZ(0, 0, 0), second_point=DB.XYZ(10, 10, 0)):
        """
        Create callout on view by params

        :param view_id: parentViewId
        :param view_type_id: viewFamilyTypeId
        :param first_point: DB.XYZ
        :param second_point: DB.XYZ

        :return: Created callout
        :rtype: MyView
        """

        callout = DB.ViewSection.CreateCallout(doc, view_id, view_type_id, first_point, second_point)
        logging.info('Callout "{} #{}" was created'.format(callout.Name, callout.Id))
        return cls(callout)

    def set_crop(self, borders):
        """
        Set crop view to given borders as CurveLoop

        :param borders: DB.CurveLoop
        """

        view_manage = self.view.GetCropRegionShapeManager()
        view_manage.SetCropShape(borders)
        logging.info('Set crop for view: {}'.format(self.view.Name))

    def calc_and_rotate(self, elem_dir, origin):
        """
        Calculate angle of rotation between current view and UpDirection of ActiveView

        And if necessary rotate view to vertical or horizontal direction

        :param elem_dir: DB.XYZ, direction view to
        :param origin: DB.XYZ, origin of view, about the center of which will rotate
        """

        angle = my_features.calc_angle_to_ver_or_hor_side(elem_dir, second_vector=self.view.UpDirection)

        if 0.02 < abs(angle) < pi - 0.02:  # 0.02 == 1 градус
            self._rotate_view(-angle, origin)

    def _rotate_view(self, angle, point):
        """
        Rotate view by angle about point and z axis

        :param angle: angle to rotation
        :type angle: float
        :param point: DB.XYZ, point about which view will rotate
        """

        crop_elem = self._find_crop_elem()
        axis = DB.Line.CreateBound(point, point + DB.XYZ.BasisZ)

        DB.ElementTransformUtils.RotateElement(doc, crop_elem, axis, angle)
        logging.debug('View was rotated to {:.2f}'.format(angle * 180 / pi))

    def _find_crop_elem(self):
        """
        For current view find crop element, which we can rotate or move

        :return: DB.Element, crop element on view
        """

        cat_filter = DB.ElementCategoryFilter(DB.BuiltInCategory.OST_Viewers)
        elems = self.view.GetDependentElements(cat_filter)
        return elems[0]

    def __getattr__(self, item):
        """
        Parameters stub
        """
        return getattr(self.view, item)

    @classmethod
    def get_any_not_active_view(cls):
        collector = DB.FilteredElementCollector(doc).OfClass(DB.ViewPlan)
        for view in collector:
            if view.Id != doc.ActiveView.Id:
                return MyView(view)
