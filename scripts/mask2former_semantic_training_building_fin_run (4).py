import json
import numpy as np
import os
import random
import requests
from io import BytesIO
from math import trunc
from PIL import Image as PILImage
from PIL import ImageDraw as PILImageDraw
from huggingface_hub import login
from transformers import Mask2FormerImageProcessor
import albumentations as A
from albumentations.pytorch import ToTensorV2
import evaluate
from huggingface_hub import HfApi, upload_file, hf_hub_download
import torch
import os
from tqdm.auto import tqdm
from datasets import load_dataset
from torch.utils.data import DataLoader

login(os.getenv("HF_TOKEN"))

dataset = load_dataset("tferhan/morocco_satellite_buildings_semantic_segmentation_512_v2", download_mode="force_redownload")

hf_hub_download(repo_id="tferhan/mask2former_semantic_ma", filename="mask2former_semantic_ma_epoch_7.pth", repo_type="model", local_dir=".")

# shuffle + split dataset
dataset = dataset.shuffle(seed=1)
dataset = dataset["train"].train_test_split(test_size=0.2)
train_ds = dataset["train"]
test_ds = dataset["test"]

labels = {"0": "background", "1" : "other", "2":"house", "3":"residential", "4":"apartments"}
id2label = {int(k): v for k, v in labels.items()}
label2id = {v: k for k, v in id2label.items()}

def color_palette():
    """Color palette that maps each class to RGB values.

    This one is actually taken from ADE20k.
    """
    return [[61, 230, 250], [255, 6, 51], [11, 102, 255],
            [255, 7, 71], [255, 9, 224], [9, 7, 230], [220, 220, 220],
            [255, 9, 92], [112, 9, 255], [8, 255, 214], [7, 255, 224],
            [255, 184, 6], [10, 255, 71], [255, 41, 10], [7, 255, 255],
            [224, 255, 8], [102, 8, 255], [255, 61, 6], [255, 194, 7],
            [255, 122, 8], [0, 255, 20], [255, 8, 41], [255, 5, 153],
            [6, 51, 255], [235, 12, 255], [160, 150, 20], [0, 163, 255],
            [140, 140, 140], [250, 10, 15], [20, 255, 0], [31, 255, 0],
            [255, 31, 0], [255, 224, 0], [153, 255, 0], [0, 0, 255],
            [255, 71, 0], [0, 235, 255], [0, 173, 255], [31, 0, 255],
            [11, 200, 200], [255, 82, 0], [0, 255, 245], [0, 61, 255],
            [0, 255, 112], [0, 255, 133], [255, 0, 0], [255, 163, 0],
            [255, 102, 0], [194, 255, 0], [0, 143, 255], [51, 255, 0],
            [0, 82, 255], [0, 255, 41], [0, 255, 173], [10, 0, 255],
            [173, 255, 0], [0, 255, 153], [255, 92, 0], [255, 0, 255],
            [255, 0, 245], [255, 0, 102], [255, 173, 0], [255, 0, 20],
            [255, 184, 184], [0, 31, 255], [0, 255, 61], [0, 71, 255],
            [255, 0, 204], [0, 255, 194], [0, 255, 82], [0, 10, 255],
            [0, 112, 255], [51, 0, 255], [0, 194, 255], [0, 122, 255],
            [0, 255, 163], [255, 153, 0], [0, 255, 10], [255, 112, 0],
            [143, 255, 0], [82, 0, 255], [163, 255, 0], [255, 235, 0],
            [8, 184, 170], [133, 0, 255], [0, 255, 92], [184, 0, 255],
            [255, 0, 31], [0, 184, 255], [0, 214, 255], [255, 0, 112],
            [92, 255, 0], [0, 224, 255], [112, 224, 255], [70, 184, 160],
            [163, 0, 255], [153, 0, 255], [71, 255, 0], [255, 0, 163],
            [255, 204, 0], [255, 0, 143], [0, 255, 235], [133, 255, 0],
            [255, 0, 235], [245, 0, 255], [255, 0, 122], [255, 245, 0],
            [10, 190, 212], [214, 255, 0], [0, 204, 255], [20, 0, 255],
            [255, 255, 0], [0, 153, 255], [0, 41, 255], [0, 255, 204],
            [41, 0, 255], [41, 255, 0], [173, 0, 255], [0, 245, 255],
            [71, 0, 255], [122, 0, 255], [0, 255, 184], [0, 92, 255],
            [184, 255, 0], [0, 133, 255], [255, 214, 0], [25, 194, 194],
            [102, 255, 0], [92, 0, 255]]

palette = color_palette()

import numpy as np
from torch.utils.data import Dataset

class ImageSegmentationDataset(Dataset):
    """Image segmentation dataset."""

    def __init__(self, dataset, transform):
        """
        Args:
            dataset
        """
        self.dataset = dataset
        self.transform = transform

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, idx):
        original_image = np.array(self.dataset[idx]['pixel_values'])
        original_segmentation_map = np.array(self.dataset[idx]['label'])

        transformed = self.transform(image=original_image, mask=original_segmentation_map)
        image, segmentation_map = transformed['image'], transformed['mask']

        # convert to C, H, W
        image = image.transpose(2,0,1)

        return image, segmentation_map, original_image, original_segmentation_map

ADE_MEAN = np.array([123.675, 116.280, 103.530]) / 255
ADE_STD = np.array([58.395, 57.120, 57.375]) / 255

train_transform = A.Compose([
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.5),
        A.RandomRotate90(p=0.5),  # only multiples of 90°, preserves shape
        A.MotionBlur(blur_limit=7, p=0.2),
        A.Sharpen(alpha=(0.1, 0.3), lightness=(0.9, 1.1), p=0.3),
        A.CLAHE(clip_limit=2.0, p=0.3),
        A.MultiplicativeNoise(multiplier=(0.9, 1.1), elementwise=True, p=0.2),
        A.Normalize(ADE_MEAN, ADE_STD),
    ])

test_transform = A.Compose([
        A.Normalize(ADE_MEAN, ADE_STD),
    ])

train_dataset = ImageSegmentationDataset(train_ds, transform=train_transform)
test_dataset = ImageSegmentationDataset(test_ds, transform=test_transform)

preprocessor = Mask2FormerImageProcessor(num_labels = 5, ignore_index=0, do_reduce_labels=False, do_resize=False, do_rescale=False, do_normalize=False)

def collate_fn(batch):
    inputs = list(zip(*batch))
    images = inputs[0]
    segmentation_maps = inputs[1]
    # this function pads the inputs to the same size,
    # and creates a pixel mask
    # actually padding isn't required here since we are cropping
    batch = preprocessor(
        images,
        segmentation_maps=segmentation_maps,
        return_tensors="pt",
    )
    device = torch.device("cuda")
    for k, v in batch.items():
        if torch.is_tensor(v):
            batch[k] = v.to(device, non_blocking=True)

    batch["original_images"] = inputs[2]
    batch["original_segmentation_maps"] = inputs[3]

    return batch

train_dataloader = DataLoader(train_dataset, batch_size=2, shuffle=True, collate_fn=collate_fn)
test_dataloader = DataLoader(test_dataset, batch_size=2, shuffle=False, collate_fn=collate_fn)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

from transformers import Mask2FormerForUniversalSegmentation
model = Mask2FormerForUniversalSegmentation.from_pretrained(
    "facebook/mask2former-swin-base-IN21k-ade-semantic",
    id2label=id2label,
    label2id=label2id,
    ignore_mismatched_sizes=True,
).to(device)

metric = evaluate.load("mean_iou")

optimizer = torch.optim.Adam(model.parameters(), lr=5e-5)

checkpoint = torch.load("best_model.pth", map_location=device)
model.load_state_dict(checkpoint["model_state_dict"])
optimizer.load_state_dict(checkpoint["optimizer_state_dict"])

model = model.to(device)

best_loss = float('inf')
best_miou = 0.0
best_epoch = -1
patience = 10
no_improve_epochs = 0
best_state = None
log_history = []
log_file = "training_log.json"

api = HfApi()

for epoch in range(11, 50):
    print(f"\nEpoch {epoch+1}/50")
    model.train()
    train_loss_sum = 0
    train_samples = 0

    for idx, batch in enumerate(tqdm(train_dataloader)):
        optimizer.zero_grad()
        outputs = model(
            pixel_values=batch["pixel_values"],
            mask_labels=[m.to(device) for m in batch["mask_labels"]],
            class_labels=[c.to(device) for c in batch["class_labels"]],
        )
        loss = outputs.loss
        loss.backward()
        optimizer.step()
        train_loss_sum += loss.item() # * batch["pixel_values"].size(0)
        train_samples += batch["pixel_values"].size(0)

    avg_train_loss = train_loss_sum / train_samples

    model.eval()
    val_loss_sum = 0
    val_samples = 0

    with torch.no_grad():
        for idx, batch in enumerate(tqdm(test_dataloader)):
            outputs = model(
                pixel_values=batch["pixel_values"],
                mask_labels=[m.to(device) for m in batch["mask_labels"]],
                class_labels=[c.to(device) for c in batch["class_labels"]],
            )
            val_loss_sum += outputs.loss.item()
            val_samples += batch["pixel_values"].size(0)

            preds = preprocessor.post_process_semantic_segmentation(
                outputs, target_sizes=[(img.shape[0], img.shape[1]) for img in batch["original_images"]]
            )
            metric.add_batch(references=batch["original_segmentation_maps"], predictions=preds)

    avg_val_loss = val_loss_sum / val_samples
    results = metric.compute(num_labels=len(id2label), ignore_index=0)
    mean_iou = results["mean_iou"]
    per_category_iou = results["per_category_iou"]
    per_category_accuracy = results["per_category_accuracy"]
    log_entry = {
    "epoch": epoch + 1,
    "train_loss": avg_train_loss,
    "val_loss": avg_val_loss,
    "mean_iou": mean_iou,
    "per_category_iou": {id2label[i]: float(v) for i, v in enumerate(per_category_iou)},
    "per_category_accuracy": {id2label[i]: float(v) for i, v in enumerate(per_category_accuracy)}
    }
    log_history.append(log_entry)
    with open(log_file, "w") as f:
        json.dump(log_history, f, indent=2)

    upload_file(
        path_or_fileobj=log_file,
        path_in_repo=log_file,
        repo_id="tferhan/mask2former_semantic_ma",
        repo_type="model"
    )


    print(f"Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f} | mIoU: {mean_iou:.4f} | per catg IoU: {per_category_iou} | per catg Acc: {per_category_accuracy}")

    improved = avg_val_loss < best_loss or mean_iou > best_miou
    if improved:
        best_loss = min(best_loss, avg_val_loss)
        best_miou = max(best_miou, mean_iou)
        best_epoch = epoch
        best_state = {
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
        }
        torch.save(best_state, "best_model.pth")
        model.save_pretrained("./best_model_hf")
        preprocessor.save_pretrained("./best_model_hf")
        print("Improvement detected — model saved.")
        no_improve_epochs = 0
    else:
        no_improve_epochs += 1
        print(f" No improvement for {no_improve_epochs} epoch(s).")
        if no_improve_epochs >= patience:
            print(f"Rolling back to epoch {best_epoch}")
            model.load_state_dict(best_state["model_state_dict"])
            optimizer.load_state_dict(best_state["optimizer_state_dict"])
            break
    if epoch % 10 == 0:
      repo_id = "tferhan/mask2former_semantic_ma"
      upload_file(path_or_fileobj="best_model.pth", path_in_repo="best_model.pth", repo_id=repo_id, repo_type="model")
      upload_file(path_or_fileobj="./best_model_hf/model.safetensors", path_in_repo="model.safetensors", repo_id=repo_id, repo_type="model")







repo_id = "tferhan/mask2former_semantic_ma"
upload_file(path_or_fileobj="best_model.pth", path_in_repo="best_model.pth", repo_id=repo_id, repo_type="model")
upload_file(path_or_fileobj="./best_model_hf/model.safetensors", path_in_repo="model.safetensors", repo_id=repo_id, repo_type="model")

os.system("sudo shutdown now")
