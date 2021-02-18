# coding=utf-8
from base.wrapper import DB, doc, Transaction
from base.exeption import ElemNotFound
from math import pi

import logging
from . import my_features, my_axles
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
        logging.debug('Set crop for view: {}'.format(self.view.Name))

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


def get_template_view_by_name(template_name):
    collector = DB.FilteredElementCollector(doc).OfClass(DB.View)

    for view in collector:
        if view.IsTemplate and view.Name == template_name:
            logging.debug('Template view with name "{}" was found'.format(template_name))
            return view

    raise ex.ElemNotFound('Template view with name "{}" not found'.format(template_name))


def get_or_create_template_by_name_and_type(template_name, view_type):
    try:
        template_view = get_template_view_by_name(template_name)
    except ex.ElemNotFound:
        logging.debug('Template view with name "{}" not found'.format(template_name))
        template_view = create_plan_template_by_name_and_type(template_name, view_type)

    return template_view


@Transaction.ensure('Create template')
def create_plan_template_by_name_and_type(template_name, view_type):
    any_view = get_any_view_by_type(view_type)
    template_view = any_view.CreateViewTemplate()

    parameters = template_view.GetTemplateParameterIds()
    template_view.SetNonControlledTemplateParameterIds(parameters)
    template_view.Name = template_name

    logging.debug('Template view was created')
    return template_view


def get_any_view_by_type(view_type):
    collector = DB.FilteredElementCollector(doc).OfClass(DB.View)

    for view in collector:
        if view.ViewType == view_type:

            logging.debug('Get any view with type: "{}"'.format(view_type))
            return view

    raise ex.ElemNotFound('Any view with type: "{}" not found'.format(view_type))


def set_template(view, template_view):
    if view.IsValidViewTemplate(template_view.Id):
        view.ViewTemplateId = template_view.Id
        logging.debug('Template was installed: {}'.format(template_view.Name))
    else:
        ex.ScriptError('Its not valid template "{}" to view "{}"'.format(template_view.Name, view.Name))


def set_visible_section_scale(view, scale=200):
    param = view.get_Parameter(DB.BuiltInParameter.SECTION_COARSER_SCALE_PULLDOWN_METRIC)
    param.Set(scale)
    logging.debug('Set visible section scale: {}'.format(scale))


def get_center_point_of_view(view):
    logging.debug('View #{}. View type is "{}"'.format(view.Id, view.ViewType))

    if view.ViewType in [DB.ViewType.Section, DB.ViewType.Elevation]:
        center_point = get_center_point_of_view_section(view)

    elif view.ViewType in [DB.ViewType.EngineeringPlan, DB.ViewType.FloorPlan]:
        center_point = get_center_point_of_plan(view)

    else:
        raise NotImplementedError('View #{}. Type "{}" is NotImplemented'.format(view.Id, view.ViewType))

    logging.debug('View #{}. Get center point ({:.1f}, {:.1f}, {:.1f}), at elevation {:.2f} m'.format(
        view.Id, center_point.X, center_point.Y, center_point.Z, center_point.Z * 0.3048))
    return center_point


def get_center_point_of_view_section(section_view):
    box = section_view.CropBox
    center_box = (box.Max + box.Min) / 2

    center_point = section_view.Origin + DB.XYZ(center_box.X, 0, center_box.Y)

    return center_point


def get_center_point_of_plan(plan_view):
    box = plan_view.CropBox
    center_box = (box.Max + box.Min) / 2

    cut_level = plan_view.GenLevel
    cut_level_elevation = cut_level.Elevation

    plan_range = plan_view.GetViewRange()
    cut_offset = plan_range.GetOffset(DB.PlanViewPlane.CutPlane)

    center_point = DB.XYZ(plan_view.Origin.X + center_box.X,
                          plan_view.Origin.Y + center_box.Y,
                          cut_level_elevation + cut_offset)

    return center_point


def duplicate_and_move_up(view, up_value):
    new_view = duplicate_view(view)
    move_view(new_view, up_value)

    duplicate_annotation(view, new_view, up_value)
    correct_axles(view, new_view, up_value)

    logging.debug('View #{}. View was copied from view #{} and move up to {:.3f} m'.format(
        new_view.Id, view.Id, up_value * 0.3048))
    return new_view


def duplicate_view(view, option=DB.ViewDuplicateOption.Duplicate):
    new_view_id = view.Duplicate(option)
    if new_view_id == DB.ElementId.InvalidElementId:
        raise ElemNotFound('View #{}. Cant duplicate view because its invalid'.format(view.Id))

    new_view = doc.GetElement(new_view_id)

    logging.debug('View #{}. Duplicate view to #{}'.format(view.Id, new_view.Id))
    return new_view


def move_view(view, up_value):
    box = view.CropBox

    vector = DB.XYZ(0, up_value, 0)

    box.Min = box.Min + vector
    box.Max = box.Max + vector

    view.CropBox = box
    logging.debug('View #{}. Was moved to {:.3f} m'.format(view.Id, up_value*304.8))


def duplicate_annotation(view, new_view, up_value):
    data = my_features.get_depends_elems_id_by_class(view, DB.FamilyInstance)
    new_data = copy_elem_on_view_to_new_view_with_up_move(data, view, new_view, up_value)

    return new_data


def correct_axles(view, new_view, up_value):
    axles = get_elem_on_view_by_category(view, DB.BuiltInCategory.OST_Grids)

    for axis in axles:
        my_axles.move_axles_crop_from_view_to_view_by_up_value(axis, view, new_view, up_value)

    logging.debug('View #{}. {} Axles crop was moved up to {:.3f} m from view#{}'.format(
        new_view.Id, len(axles), up_value * 0.3048, view.Id))


def get_elem_on_view_by_category(view, category):
    elements = DB.FilteredElementCollector(doc, view.Id).OfCategory(category).ToElements()

    logging.debug('View #{}. Get {} elems on view by category: {}'.format(view.Id, len(elements), category))
    return elements


def copy_elem_on_view_to_new_view_with_up_move(elems_id, view, new_view, up_value=0, option=None):
    transform = DB.Transform.CreateTranslation(DB.XYZ(0, 0, up_value)) if up_value else None

    new_ids = DB.ElementTransformUtils.CopyElements(view, elems_id, new_view, transform, option)

    logging.debug('View #{}. Copy {} elems from view #{}'.format(new_view.Id, len(new_ids), view.Id))
    return new_ids
