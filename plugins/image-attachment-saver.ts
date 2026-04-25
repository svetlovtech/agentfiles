/**
 * Image Attachment Saver Plugin for OpenCode
 *
 * When a user pastes/sends an image in the OpenCode web chat, the image
 * is stored only as a base64 data URI in the SQLite database. This plugin
 * intercepts the message.part.updated event, extracts the image data,
 * saves it to disk, and injects the file path back into the conversation
 * so that MCP vision tools (like zai-mcp-server) can access it.
 *
 * Supported sources:
 *   - Clipboard paste (data:image/...;base64,...)
 *   - File reference (file:///path/to/file)
 *   - HTTP/HTTPS URL (https://...)
 *
 * Saved to: /tmp/opencode-images/<partId>.<ext>
 */

import type { Plugin } from "@opencode-ai/plugin";
import { writeFile, mkdir } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";

const IMAGE_DIR = join(tmpdir(), "opencode-images");
const MIME_TO_EXT: Record<string, string> = {
  "image/png": "png",
  "image/jpeg": "jpg",
  "image/jpg": "jpg",
  "image/gif": "gif",
  "image/webp": "webp",
  "image/svg+xml": "svg",
  "image/bmp": "bmp",
  "image/avif": "avif",
  "image/heic": "heic",
};

function getExtension(mime: string): string {
  return MIME_TO_EXT[mime] || mime.split("/")[1] || "bin";
}

export const ImageAttachmentSaver: Plugin = async ({ client }) => {
  // Ensure temp directory exists
  await mkdir(IMAGE_DIR, { recursive: true });

  return {
    event: async ({ event }) => {
      // Only handle message part updates
      if (event.type !== "message.part.updated") return;

      const part = event.properties.part as any;
      if (!part || part.type !== "file") return;
      if (!part.mime?.startsWith("image/")) return;

      let localPath: string | null = null;

      try {
        // Case 1: file:/// URI — already on disk
        if (part.url.startsWith("file://")) {
          localPath = decodeURIComponent(part.url.slice(7));
        }
        // Case 2: data:image/...;base64,... — clipboard paste
        else if (part.url.startsWith("data:")) {
          const match = part.url.match(/^data:([^;]+);base64,(.+)$/);
          if (match) {
            const ext = getExtension(match[1]);
            const filename = part.filename || `${part.id}.${ext}`;
            localPath = join(IMAGE_DIR, filename);
            const buffer = Buffer.from(match[2], "base64");
            await writeFile(localPath, buffer);
          }
        }
        // Case 3: http(s):// URL — download
        else if (part.url.startsWith("http://") || part.url.startsWith("https://")) {
          const response = await fetch(part.url);
          if (response.ok) {
            const ext = getExtension(part.mime);
            const filename = part.filename || `${part.id}.${ext}`;
            localPath = join(IMAGE_DIR, filename);
            const buffer = Buffer.from(await response.arrayBuffer());
            await writeFile(localPath, buffer);
          }
        }
      } catch (err: any) {
        await client.app.log({
          service: "image-saver",
          level: "error",
          message: `Failed to save image: ${err.message}`,
        });
        return;
      }

      if (localPath) {
        await client.app.log({
          service: "image-saver",
          level: "info",
          message: `Image saved to: ${localPath}`,
          extra: { filename: part.filename, mime: part.mime, source: part.url.startsWith("data:") ? "clipboard" : part.url.startsWith("file://") ? "file" : "url" },
        });
      }
    },
  };
};

export default ImageAttachmentSaver;
