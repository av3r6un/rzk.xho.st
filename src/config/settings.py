from yaml import safe_load
from pathlib import Path
import os


class Settings:
  CONFIG_FOLDER = Path(os.path.abspath(os.path.abspath(os.path.dirname(__file__))))
  SETTINGS_FP = os.path.abspath(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'settings.yaml'))
  
  def __init__(self):
    self._load_settings()
    self._load_extra()
    
  def _load_settings(self):
    with open(self.SETTINGS_FP, 'r', encoding='utf-8') as f:
      data = safe_load(f)
    self.__dict__.update(data or {})
    for key in list(self.__dict__.keys()):
      if key.isupper() and key in os.environ:
        self.__dict__[key] = os.environ[key]

  def _load_extra(self):
    extra_files = (os.getenv('EXTRA_FILES') or '').split(',')
    for file in extra_files:
      file = file.strip()
      if not file:
        continue
      if not os.path.exists(self.CONFIG_FOLDER / file): raise FileNotFoundError(f'extra file {file} not found!')
      extra_key = file.split('.')[0]
      with open(self.CONFIG_FOLDER / file, 'r', encoding='utf-8') as f:
        data = safe_load(f)
      self.__dict__[extra_key.upper()] = data
        
