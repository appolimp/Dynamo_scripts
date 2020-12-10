# coding=utf-8
from my_class.base.wrapper import Transaction, doc, DB, transaction_group
from my_class.base.exeption import ScriptError, ElemNotFound, NotValidValue
import logging
import os


def main():
    PARAM_NAME = IN[0]
    PATH = IN[1]
    logging.debug('Start with param:\nParam_name == "{}", \npath == "{}"'.format(PARAM_NAME, PATH))

    data = get_data_from_file(PATH)

    count = 0
    for (id_elem, value) in data:
        try:
            fill_by_id(id_elem, value, PARAM_NAME)
            count += 1

        except (ElemNotFound, NotValidValue) as err:
            logging.error(err.args[0])

    logging.info('Fill param "{}" to {} elements'.format(PARAM_NAME, count))


def get_data_from_file(path):
    if os.path.isfile(path):
        logging.debug('File "{}" was found'.format(os.path.split(path)[-1]))

        with open(path) as f:
            f.readline()
            valid_data = convert_to_valid_data(f)

        return valid_data

    raise ElemNotFound('File not found by path: "{}"'.format(path))


def convert_to_valid_data(f):
    data = []
    errors = 0
    for line in f:
        valid_values = get_valid_values(line.strip())

        if valid_values:
            data.append(valid_values)
        else:
            logging.error('Line is not valid: "{}"'.format(line))

    logging.debug('Find {} valid values, and {} error'.format(len(data), errors))
    return data


def get_valid_values(text):
    left, par, right = text.partition(', ')
    if left and right:
        return left, right


def fill_by_id(id, value, param_name):
    elem = get_element_by_id(id)
    param = get_param_elem_by_name(elem, param_name)
    set_value_param(param, value)
    logging.debug('Set param "{}" value == "{}" to element with id #{}'.format(param_name, value, id))


def get_element_by_id(id):
    if not(id is int or id.isdigit()):
        raise NotValidValue('Id #{} is not int or digit'.format(id))

    elem_id = DB.ElementId(int(id))
    element = doc.GetElement(elem_id)

    if element is None:
        raise ElemNotFound('Element with id #{} not found'.format(id))

    logging.debug('Element was found: ' + str(element))
    return element


def get_param_elem_by_name(elem, param_name):
    params = elem.GetParameters(param_name)
    if params and len(params) == 1:
        logging.debug('Param with name "{}" was found'.format(param_name))
        return params[0]
    elif params:
        logging.error('Get some param with name: {}'.format(param_name))
        return params[0]
    else:
        raise ElemNotFound('Param with name "{}" not found'.format(param_name))


def set_value_param(param, value):
    if param.StorageType == DB.StorageType.String:
        param.Set(str(value))
    else:
        raise NotValidValue('Param storage type is not String, and equal {}'.format(param.StorageType))


if __name__ == '__main__':
    logging.basicConfig(
        filename=None, level=logging.INFO,
        format='[%(asctime)s] %(levelname).1s: %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S')

    try:
        main()
    except ScriptError as e:
        logging.error(e)
    except Exception as err:
        logging.exception('Critical error: ' + str(err.args[0]))
