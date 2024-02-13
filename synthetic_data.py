import argparse
import numpy as np
import pathlib
import tifffile

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input', type=str, required=True)
parser.add_argument('-o', '--output', type=str, required=True)
parser.add_argument('-d', '--dimension', type=int, choices=[2, 3], required=True)
parser.add_argument('-s', '--scale_factor', type=float, default=10.0)
parser.add_argument('-f', '--fluorophores', type=int, default=1)
args = parser.parse_args()

input_path = pathlib.Path(args.input)
output_path = pathlib.Path(args.output)

if args.scale_factor <= 1.0:
    raise ValueError('Scale factor must exceed 1.0')

if not output_path.exists():
    print('Creating output directory', output_path)
    output_path.mkdir(parents=True)

output_gt_path = output_path.joinpath('GT')
output_raw_path = output_path.joinpath('Raw')
if not output_gt_path.exists():
    print('Creating GT directory', output_gt_path)
    output_gt_path.mkdir(parents=True)
if not output_raw_path.exists():
    print('Creating Raw directory', output_raw_path)
    output_raw_path.mkdir(parents=True)

if not output_path.is_dir():
    raise ValueError('Output path should be a directory')

if input_path.is_dir():
    data = sorted(input_path.glob('*.tif'))
else:
    data = [input_path]

rng = np.random.default_rng(seed=13022024)


def save_image_pair(gt_img, output_path, name, img_idx):
    noised_img = np.uint16(rng.poisson(gt_img / args.scale_factor))
    tifffile.imwrite(f"{output_gt_path}/{name}_{img_idx}_gt.tif", gt_img, imagej=True)
    tifffile.imwrite(f"{output_raw_path}/{name}_{img_idx}_noisy.tif", noised_img, imagej=True)


for img_file in data:
    gt = tifffile.imread(img_file)
    if len(gt.shape) != args.dimension + 1:
        raise ValueError('Mismatch between specified dimensions and true image dimensions')
    for i in range(gt.shape[0]):
        save_image_pair(gt[i, ...], output_path, img_file.with_suffix('').name, i)
