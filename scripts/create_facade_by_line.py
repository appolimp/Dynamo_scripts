# coding=utf-8
from base.wrapper import transaction, doc, DB, uidoc
from base.exeption import ScriptError
from base.selection import get_selected
from Autodesk.Revit.UI.Selection import ISelectionFilter
from System.Collections.Generic import List
from math import pi
import logging


class MyFilter(ISelectionFilter):
    """
    Custom filter for uidoc.Selection, which allows the user to select elements of a specific category

    """
    def __init__(self, category):
        ISelectionFilter.__init__(self)
        self._cat = getattr(DB.BuiltInCategory, category)
        self._cat_id = DB.Category.GetCategory(doc, self._cat).Id

    def AllowElement(self, elem):
        """
        Allow selected element of a specific category

        :param elem: Element
        :type elem: DB.Element
        :return: True or False
        :rtype: bool
        """
        if elem.Category.Id == self._cat_id:
            return True
        return False


def main():
    """
    Create elevation view by detail lines on right or left side.

    If required, can delete all elevation views selected during startup

    Accepts input:
        OFFSET: Indent from line

        HEIGHT: Height view section

        SHIFT: Shift view section border to side

        DEPTH: offset far clip for view section

        RIGHT_SIDE: Side of line for new elevation marker, that are turned to the line

        DELETE_ELEV_IN_SELECTION: Delete or not selected elevation views

    :return: list of ViewSection
    :rtype: list(DB.ViewSection)
    """

    # TODO add task_dialog

    OFFSET = IN[0]
    HEIGHT = IN[1]
    SHIFT = IN[2]
    DEPTH = IN[3]
    RIGHT_SIDE = IN[4]
    DELETE_ELEV_IN_SELECTION = IN[5]

    if not RIGHT_SIDE:
        OFFSET = - OFFSET

    if DELETE_ELEV_IN_SELECTION:
        delete_all_elevation_marker_on_selection()

    lines = request_user_to_select_detail_line()
    elev_list = create_elev_view_by_detail_lines(lines, offset=OFFSET, height=HEIGHT,
                                                 shift=SHIFT, depth=DEPTH, right=RIGHT_SIDE)

    return elev_list


def create_elev_view_by_detail_lines(lines, offset, height, shift, depth, right):
    """
    Create List[ViewSection] by line

    By calling create_elev_view_by_detail_line(...) for each line in lines

    :param lines: Lines for section
    :type lines: list[DB.Line]
    :param offset: Indent from line
    :type offset: int or float
    :param height: Height view section
    :type height: int or float
    :param shift: Shift view section border to side
    :type shift: int or float
    :param depth: offset far clip for view section
    :type depth: int or float
    :param right: Side of line for new elevation marker, that are turned to the line
    :type right: bool

    :return: list of ViewSection
    :rtype: list(DB.ViewSection)
    """

    elev_list = []
    for line in lines:
        elev = create_elev_view_by_detail_line(line, offset=offset, height=height,
                                               shift=shift, depth=depth, right=right)
        elev_list.append(elev)

    logging.info('All ViewSections are created, in the amount of #{} pieces '.format(len(elev_list)))

    return elev_list


@transaction
def create_elev_view_by_detail_line(line, offset, height, shift, depth, right):
    """
    Create ViewSection by line

    Also by offset, height, shift, depth, right side

    :param line: Line for section
    :type line: DB.Line
    :param offset: Indent from line
    :type offset: int or float
    :param height: Height view section
    :type height: int or float
    :param shift: Shift view section border to side
    :type shift: int or float
    :param depth: offset far clip for view section
    :type depth: int or float
    :param right: Side of line for new elevation marker, that are turned to the line
    :type right: bool

    :return: ViewSection
    :rtype: DB.ViewSection
    """

    per = get_normal_by_line(line)
    start_crop, middle_crop, end_crop = map(lambda p: transform_point(p, per, offset), get_start_middle_end_point(line))

    marker = create_elevation_marker(middle_crop)
    elev = marker.CreateElevation(doc, doc.ActiveView.Id, 0)
    set_depth_section_for_view(elev, depth)

    angle = calc_angle(per, DB.XYZ.BasisX)
    if not right:
        angle += pi

    rotate_element(marker, middle_crop, angle)

    crop_region = create_shifted_crop_region_by_points_and_height(start_crop, end_crop, height, shift)
    set_crop_for_elev(elev, crop_region)

    logging.info('Create new ViewSection "{}" #{}'.format(elev.Name, elev.Id))

    return elev


def request_user_to_select_detail_line():
    """
    Request user to select detail lines by rectangle

    :return: Lines, which user select
    :rtype: list
    """

    lines_filter = MyFilter('OST_Lines')
    lines = uidoc.Selection.PickElementsByRectangle(lines_filter, 'Select detail lines')

    logging.info('User select {} detail lines'.format(len(lines)))

    return lines


def get_start_middle_end_point(line):
    """
    Ger three point on line
    Transform it to DB.Curve

    :param line: Line
    :type line: DB.Line
    :return: Start, middle and end point of line
    :rtype: [DB.XYZ, DB.XYZ, DB.XYZ]
    """
    curve = line.GeometryCurve
    start = curve.GetEndPoint(0)
    end = curve.GetEndPoint(1)
    middle = (start + end)/2
    return start, middle, end


def create_elevation_marker(origin, scale=100):
    """
    Create ElevationMarker by origin and scale new view

    :param origin: Origin point for marker
    :type origin: DB.XYZ
    :param scale: Scale all new view for elevation marker
    :type scale: int
    :return: ElevationMarker
    :rtype: DB.ElevationMarker
    """

    view_fam_type_id = get_view_family_type_id(DB.ViewFamily.Elevation)
    marker = DB.ElevationMarker.CreateElevationMarker(doc, view_fam_type_id, origin, scale)

    logging.info('Create new ElevationMarker "{}" #{}'.format(marker.Name, marker.Id))
    return marker


def get_view_family_type_id(view_family):
    """
    Get ViewFamilyType.Id on document by ViewFamily

    :param view_family: ViewFamily (enum)
    :type view_family: DB.ViewFamily
    :return: ViewFamilyType.Id
    :rtype: DB.ElementId
    """

    view_family_types = DB.FilteredElementCollector(doc).OfClass(DB.ViewFamilyType).ToElements()
    for view_family_type in view_family_types:
        if view_family_type.ViewFamily == view_family:
            return view_family_type.Id

    raise NotImplemented


@transaction
def delete_all_elevation_marker_on_selection():
    """
    Delete all elevation marker on selected users

    """
    count = 0
    for el in get_selected():
        if el and el.Category.Id == DB.Category.GetCategory(doc, DB.BuiltInCategory.OST_Elev).Id:
            count += 1
            doc.Delete(el.Id)

    logging.info('Delete #{} elevation marker'.format(count))


def set_depth_section_for_view(view, depth):
    """
    Set offset far clip for view

    :param view: Section view
    :type view: DB.ViewSection
    :param depth: Value of offset far clip
    :type depth: int or float
    """

    param_depth = view.get_Parameter(DB.BuiltInParameter.VIEWER_BOUND_OFFSET_FAR)
    param_depth.Set(depth)

    logging.debug('Set offset far clip for view "{}" #{} to {:.2f}'.format(view.Name, view.Id, float(depth)))


def rotate_element(element, point, angle):
    """
    Rotate element by middle point and angle

    :param element: Element for rotation
    :type element: DB.Element
    :param point: Point of rotation
    :type point: DB.XYZ
    :param angle: Angle of rotation as radian
    :type angle: int or float
    """
    axis = DB.Line.CreateBound(point, point + DB.XYZ.BasisZ)
    DB.ElementTransformUtils.RotateElement(doc, element.Id, axis, angle)

    logging.debug('The element is rotated about a point [{:.1f}, {:.1f}, {:.1f}] by {:.1f} degrees'.format(
        point.X, point.Y, point.Z, angle * 180 / pi))


def calc_angle(per, line):
    """
    Calculate angle between two vector.
    Take into consideration a quarter circle

    :param per: first vector
    :type per: DB.XYZ
    :param line: second vector
    :type line: DB.XYZ
    :return: Angle between [-pi, pi]
    :rtype: float
    """
    return (1 if per.Y >= 0 else -1) * per.AngleTo(line)


def get_normal_by_line(line):
    """
    Get normal to line

    :param line: Detail line
    :type line: DB.Line
    :return: Normal Vector
    :rtype: DB.XYZ
    """

    start, _, end = get_start_middle_end_point(line)
    line_dir = start - end
    norm = DB.XYZ.BasisZ.CrossProduct(line_dir).Normalize()
    return norm


def transform_point(point, direction, value):
    """
    Moves point in direction

    :param point: Point for movement
    :type point: DB.XYZ
    :param direction: Direction of movement. Vector
    :type direction: DB.XYZ
    :param value: The amount of movement
    :type value: int or float
    :return: New moved point
    :rtype: DB.XYZ
    """
    return point + direction * value


def create_shifted_crop_region_by_points_and_height(start, end, height, shift):
    """
    Create vertical rectangle of DB.CurveLoop by first and second point and height.
    Also shift out corner point

    :param start: First point of crop region border
    :type start: DB.XYZ
    :param end: Second point of crop region border
    :type end: DB.XYZ
    :param height: Height of crop region border
    :type height: int or float
    :param shift: Shift first and second points of crop region border
    :type shift: int or float
    :return: Rectangle lines of CurveLoop
    :rtype: DB.CurveLoop
    """

    line_dir = (end - start).Normalize()
    start_shifted = start - line_dir * shift
    end_shifted = end + line_dir * shift

    curves = List[DB.Curve]()

    curves.Add(DB.Line.CreateBound(start_shifted, end_shifted))
    curves.Add(DB.Line.CreateBound(end_shifted, end_shifted + DB.XYZ.BasisZ*height))
    curves.Add(DB.Line.CreateBound(end_shifted + DB.XYZ.BasisZ * height, start_shifted + DB.XYZ.BasisZ * height))
    curves.Add(DB.Line.CreateBound(start_shifted + DB.XYZ.BasisZ * height, start_shifted))

    curve_loop = DB.CurveLoop.Create(curves)

    logging.debug('Crop region of CurveLoop are created with {} lines'.format(len(curves)))

    return curve_loop


@transaction
def set_crop_for_elev(elev, crop_region):
    """
    Set crop region for ViewSection

    :param elev: View section
    :type elev: DB.ViewSection
    :param crop_region: Rectangle crop region
    :type crop_region: DB.CurveLoop
    """
    crop_manager = elev.GetCropRegionShapeManager()
    crop_manager.SetCropShape(crop_region)
    logging.debug('Crop region are set for the section view "{}" #{}'.format(elev.Name, elev.Id))


if __name__ == '__main__':
    logging.basicConfig(
        filename=None, level=logging.INFO,
        format='[%(asctime)s] %(levelname).1s <example>: %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S')

    try:
        OUT = main()
    except ScriptError as e:
        logging.error(e)
    except Exception as err:
        logging.exception('Critical error')
