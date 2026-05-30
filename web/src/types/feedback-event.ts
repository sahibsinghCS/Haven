export type FeedbackEventSource = "telegram" | "web"

export interface LiveFeedbackEvent {
  source: FeedbackEventSource
  correctionId: string
  createdAt: string
  predictedLabel: string
  correctedLabel: string
  confirmed: boolean
  notes: string
  screenshotCount: number
  memoryExamples: number
  autoRetrainEnabled: boolean
  screenshotUrl: string
}
