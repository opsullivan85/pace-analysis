#!/usr/bin/env python3
"""
ROS1 Bag File Time Extractor

This script reads ROS1 bag files from a directory and outputs a CSV file
containing the bag filename, first message timestamp, and last message timestamp
in epoch time.

Requirements:
    pip install rosbag

Usage:
    python time_checker.py /path/to/bag/directory
"""

import os
import sys
import csv
import argparse
from pathlib import Path
import rosbag
import rospy
from rospy import Time


def get_bag_time_info(bag_path):
    """
    Extract first and last message timestamps from a ROS bag file.

    Args:
        bag_path (str): Path to the bag file

    Returns:
        tuple: (first_timestamp, last_timestamp) in epoch time, or (None, None) if error
    """
    try:
        with rosbag.Bag(bag_path, "r") as bag:
            # Get bag info
            info = bag.get_type_and_topic_info()

            # If bag is empty, return None values
            if not info.topics:
                print(f"Warning: {bag_path} appears to be empty")
                return None, None

            # Get start and end times from bag info
            start_time = bag.get_start_time()
            end_time = bag.get_end_time()

            return start_time, end_time

    except Exception as e:
        print(f"Error processing {bag_path}: {str(e)}")
        return None, None


def process_bag_directory(directory_path, output_csv):
    """
    Process all bag files in a directory and write results to CSV.

    Args:
        directory_path (str): Path to directory containing bag files
        output_csv (str): Path to output CSV file
    """
    # Find all .bag files in the directory
    bag_files = []
    directory = Path(directory_path)

    if not directory.exists():
        print(f"Error: Directory {directory_path} does not exist")
        return

    for bag_file in directory.glob("*.bag"):
        bag_files.append(bag_file)

    if not bag_files:
        print(f"No .bag files found in {directory_path}")
        return

    print(f"Found {len(bag_files)} bag files")

    # Process each bag file and collect results
    results = []

    for bag_file in sorted(bag_files):
        print(f"Processing: {bag_file.name}")

        first_time, last_time = get_bag_time_info(str(bag_file))

        results.append(
            {
                "bag_filename": bag_file.name,
                "first_timestamp_epoch": first_time,
                "last_timestamp_epoch": last_time,
            }
        )

    # Write results to CSV
    with open(output_csv, "w", newline="") as csvfile:
        fieldnames = ["bag_filename", "first_timestamp_epoch", "last_timestamp_epoch"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for result in results:
            writer.writerow(result)

    print(f"Results written to {output_csv}")
    print(f"Processed {len(results)} bag files")


def main():
    parser = argparse.ArgumentParser(
        description="Extract timing information from ROS1 bag files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python bag_time_extractor.py /path/to/bags
    python bag_time_extractor.py /path/to/bags --output results.csv
        """,
    )

    parser.add_argument("directory", help="Directory containing ROS bag files")

    parser.add_argument(
        "--output",
        "-o",
        default="bag_timestamps.csv",
        help="Output CSV filename (default: bag_timestamps.csv)",
    )

    args = parser.parse_args()

    # Process the bag files
    process_bag_directory(args.directory, args.output)


if __name__ == "__main__":
    main()
