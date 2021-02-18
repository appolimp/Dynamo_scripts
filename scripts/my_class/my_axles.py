from base.wrapper import DB, app, doc
from base.exeption import ElemNotFound
import logging


def move_axles_crop_from_view_to_view_by_up_value(axis, old_view, new_view, up_value):
    old_curves = axis.GetCurvesInView(DB.DatumExtentType.ViewSpecific, old_view)

    if len(old_curves) > 1:
        logging.error('Axis #{}. Have {} curves on view #{}'.format(axis.Id, len(old_curves), old_view.Id))

    old_curve = old_curves[0]
    new_curve = move_curve_to_up_value(old_curve, up_value)

    axis.SetCurveInView(DB.DatumExtentType.ViewSpecific, new_view, new_curve)
    # logging.debug('Axis #{}. Crop was moved up to {:.3f} m on view #{}'.format(
        # axis.Id, up_value * 0.3048, new_view.Id))


def move_curve_to_up_value(curve, up_value):
    vector = DB.XYZ(0, 0, up_value)
    tf = DB.Transform.CreateTranslation(vector)

    new_curve = curve.CreateTransformed(tf)
    return new_curve
