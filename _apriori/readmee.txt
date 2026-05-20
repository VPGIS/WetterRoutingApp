IN PS
wsl --install
exit zum usegho


-> terminal -> new tab -> ubuntu


---
AB DO LINUX

python3 -m venv ~/meteodata-lab-env
source ~/meteodata-lab-env/bin/activate

pip install --upgrade pip
pip install "meteodata-lab[polytope,regrid]"


---
optional
git clone https://github.com/MeteoSwiss/meteodata-lab.git
cd meteodata-lab


---
witeri packs (alles im env):
sudo apt update && sudo apt install gdal-bin libgdal-dev libproj-dev proj-bin libspatialindex-dev libgeos-dev
->
pip install earthkit earthkit-plots rasterio eccodes xarray pandas cartopy geopandas matplotlib


---
pip install ipykernel
python -m ipykernel install --user --name=meteodata-lab-env --display-name="Meteodata Lab (venv)"


---
source ~/meteodata-lab-env/bin/activate
cd ~/meteodata-lab-env
code .

