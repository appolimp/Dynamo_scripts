# coding=utf-8
from base.wrapper import transaction, doc, DB
from base.exeption import ScriptError
from System.Collections.Generic import List
import logging


def main():
    NAME_FILTER = IN[0]
    del_filter_name_start_with(NAME_FILTER)


@transaction
def del_filter_name_start_with(filter_name):
    try:
        filters = [fil.Id for fil in filter_start_with(filter_name)]
    except KeyError:
        return
    filters_list = List[DB.ElementId](filters)
    doc.Delete(filters_list)
    logging.info("Filters, which names start with '{}', delete: {} pieces".format(filter_name, len(filters)))


def filter_start_with(filter_name):
    data = DB.FilteredElementCollector(doc).OfClass(DB.ParameterFilterElement).WhereElementIsNotElementType()
    found = False
    for el in data:
        if el.Name.startswith(filter_name):
            logging.debug("Find filter '{}' #{}".format(el.Name, el.Id))
            found = True
            yield el

    if found:
        raise StopIteration

    logging.info("Project doesn't have a filter, which start with '{}'".format(filter_name))
    raise KeyError('Filter not Found')


if __name__ == '__main__':
    logging.basicConfig(
        filename=None, level=logging.INFO,
        format='[%(asctime)s] %(levelname).1s <my_script>: %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S')

    try:
        main()
    except ScriptError as e:
        logging.error(e)
    except Exception as err:
        logging.exception('Critical error')
