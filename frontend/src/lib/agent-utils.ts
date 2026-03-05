/**
 * Strip <action>...</action> XML blocks from AI text for display.
 */
export function stripActionTags(text: string): string {
  return text.replace(/<action\s[^>]*>[\s\S]*?<\/action>/g, "").trim();
}
