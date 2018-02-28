import ddt


def tuplify(data):
  for key, value in data.items():
    if isinstance(value, dict):
      for keykey in tuplify(value):
        yield (key,) + keykey
    else:
      yield (key, value)


def unwrap(data):
  """Method decorator to add to your test methods.

  Should be added to methods of instances of ``unittest.TestCase``.
  """
  def wrapper(func):
    return ddt.data(*tuplify(data))(ddt.unpack(func))
  return wrapper
