from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict, Generator, List
from abc import ABC
import requests

from requests.api import request
from .datatypes import ImageAnnotationFile
import darwin
import darwin.importer as importer
from darwin.client import Client
from darwin.importer import formats
import itertools


class Parser(ABC):
    ALLOWED_PATHS = ["/train", "/test", "/val"]

    def __init__(
        self,
        images_dir: Path,
        annotation_dir: Path,
        dataset_name: str,
        path: str = "/train",
    ):
        self.images_dir = images_dir
        self.annotation_dir = annotation_dir
        self.dataset_name = dataset_name

        if path not in self.ALLOWED_PATHS:
            raise ValueError(f"path should be one of {self.ALLOWED_PATHS}")

        self.path = path

        self.images_dir.mkdir(exist_ok=True, parents=True)
        self.annotation_dir.mkdir(exist_ok=True, parents=True)

    @abstractmethod
    def parse_annotation(self, *args: Any, **kwargs: Any) -> ImageAnnotationFile:
        """Parse one single annotation and return a darwin annotation file"""

    @abstractmethod
    def parse(self, root: Path):
        """Parse all the files contained in root"""

    def upload(self, api_key: str):
        """Handy function to upload images and annotations to darwin in one go

        Args:
            api_key (str): A valid API KEY
            dataset_name (str): The dataset name
            images_dir (Path): The images' directory
            annotation_dir (Path): The annnotations' directory
        """
        images: List[Path] = list(self.images_dir.glob("*"))
        annotations: List[Path] = list(self.annotation_dir.glob("*.json"))

        self.upload_from_files(api_key, images, annotations)

    def upload_from_files(
        self, api_key: str, images: List[Path], annotations: List[Path]
    ):
        client = Client.from_api_key(api_key)
        dataset_identifier = f"{client.default_team}/{self.dataset_name}"
        try:
            dataset = client.create_dataset(self.dataset_name)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 422:
                dataset = client.get_remote_dataset(dataset_identifier)
            else:
                print("boom")
        # dataset.push(images, path=self.path)
        importer.import_annotations(
            dataset,
            formats.darwin.parse_file,
            annotations,
            append=True,
        )

    def upload_sample(self, api_key: str, n_samples: int = 10):
        """

        Args:
            api_key (str): A valid API KEY
            n_samples (int, optional): Number of image/annotation pairs you what to upload. Defaults to 10.
        """
        # get n_samples annotation files
        annotations_paths: List[Path] = list(
            itertools.islice(self.annotation_dir.glob("*.json"), n_samples)
        )

        annotations: List[Dict] = [
            json.load(ann_path.open("r")) for ann_path in annotations_paths
        ]
        images: List[Path] = [
            self.images_dir / Path(ann["image"]["original_filename"])
            for ann in annotations
        ]

        # I am not closing the files pointers!!
        self.upload_from_files(api_key, images, annotations_paths)
