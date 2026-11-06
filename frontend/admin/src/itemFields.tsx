import type { UploadFile } from "antd";
import type { MediaAsset } from "./api";
export type ImageFile = UploadFile<MediaAsset> & { reference?: string; uncertain?: boolean; uploadId?: string };
