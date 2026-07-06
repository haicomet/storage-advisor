# Storage Advisor

### Context: 
Digital storage requirements continue to grow as users create and retain increasing amounts of documents, photos, videos, applications, and other files. At the same time, storage has become an increasingly valuable resource, with higher-capacity devices carrying significant cost premiums and organizations spending substantial amounts maintaining large-scale storage infrastructure.
Most users have little visibility into how their storage is being used beyond basic disk usage statistics. Operating systems can identify which folders consume the most space, but they provide little insight into which files are actively used, which have become stale, or which may no longer provide value.
This challenge extends beyond personal devices. In industry, organizations often accumulate large amounts of inactive data that must eventually be migrated to lower-cost storage tiers or maintained indefinitely because determining what is truly important is difficult.
The goal of this project is to explore whether intelligent analysis of filesystem metadata and usage patterns can help users better understand and manage their local storage.
### Proposed Solution: 
Develop a macOS storage advisor that analyzes filesystem metadata to provide intelligent insights into a user's storage habits. Rather than simply reporting disk usage, the system identifies patterns such as inactive files, duplicate content, stale downloads, and storage growth trends to help users make informed storage management decisions.
## Infrastructure Components
### Desktop Application: 
A React (TypeScript) user interface packaged as a native macOS application using Tauri.
### Backend: 
A local Python 3 server utilizing FastAPI to handle the heavy computational lifting of disk analysis asynchronously, preventing UI blocking.
### Database: 
SQLite, acting as a lightweight, local repository to store file metadata (sizes, dates, paths). This tracks historical data and prevents the need to rescan the entire drive from scratch on every launch.
### Filesystem Access: 
Python's built-in os and pathlib modules, bridging with native macOS File System APIs to securely and efficiently gather file statistics.
## System Architecture
### Data Ingestion Pipeline: 
This pipeline handles the collection and storage of filesystem data. A Python-based scanning engine recursively traverses designated macOS directories to extract metadata for each file, such as its absolute path, size, creation date, and last accessed timestamp. Once extracted, this metadata is batch-processed and written to the local SQLite database, establishing a historical snapshot of the user's storage footprint.

### Data Retrieval Pipeline: 
This pipeline handles user interaction and analytics. When the user opens the React desktop application, the frontend issues asynchronous HTTP requests to the local Python FastAPI server. The backend processes these requests by querying the SQLite database and executing analytical algorithms—such as identifying duplicate files via size and hash grouping, and flagging large, inactive directories as candidates for migration to secondary or archival storage (e.g., external drives for personal use or lower-cost cloud tiers for organizations). It then serializes these insights into a clean JSON response, which the React UI consumes to render interactive charts and actionable storage metrics.





