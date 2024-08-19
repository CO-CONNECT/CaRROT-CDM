import os
import json
    
def load_json(f_in):
  if os.path.exists(f_in):
    data = json.load(open(f_in))
  else:
    try:
      data = json.loads(f_in)
    except Exception as err:
      raise FileNotFoundError(f"{f_in} not found. Or cannot parse as json")

  return data

