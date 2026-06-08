"""Haven Telegram bot: natural-language corrections → live snapshot + retrain."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional

from roomos.integrations.telegram_nl import (
    ROOM_ACTIVITY_LABELS,
    TelegramLabelParse,
    bot_user_id_from_token,
    parse_allowed_chat_ids,
    parse_correction_text,
)
from roomos.integrations.telegram_preferences_nl import parse_preference_text
from roomos.preferences.document import PreferenceValidationError, resolve_active_preset_id
from roomos.utils.logging import get_logger

from .core.config import settings
from .core.state import state
from .feedback_broadcast import publish_feedback_result
from .preferences_service import apply_and_save_preferences, load_preferences

log = get_logger("roomos.telegram")

_application: Any = None

AwaitableReply = Callable[..., Any]


def _telegram_ready() -> bool:
    if not settings.telegram_enabled:
        return False
    if not (settings.telegram_bot_token or "").strip():
        return False
    return bool(parse_allowed_chat_ids(settings.telegram_allowed_chat_ids))


def _allowed(chat_id: int) -> bool:
    return chat_id in parse_allowed_chat_ids(settings.telegram_allowed_chat_ids)


def _label_keyboard():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    row = [
        InlineKeyboardButton(label.capitalize(), callback_data=f"label:{label}")
        for label in ROOM_ACTIVITY_LABELS
    ]
    return InlineKeyboardMarkup([row])


def _predicted_label() -> Optional[str]:
    snap = state.hub.latest
    if snap is None:
        return None
    return str(getattr(snap, "primary_state", None) or "")


def _read_correction_jpeg(correction_id: str) -> Optional[bytes]:
    if state.engine is None:
        return None
    return state.engine.feedback_correction_jpeg(correction_id)


async def _send_correction_photo(reply_message: Any, correction_id: str, caption: str) -> None:
    data = await asyncio.to_thread(_read_correction_jpeg, correction_id)
    if not data:
        return
    from telegram import InputFile

    await reply_message.reply_photo(
        photo=InputFile(data, filename="haven_snapshot.jpg"),
        caption=caption[:1024],
    )


async def _apply_label(
    *,
    chat_id: int,
    label: str,
    notes: str,
    reply: AwaitableReply,
    reply_message: Any = None,
) -> None:
    if state.engine is None:
        await reply("Haven is not running. On your PC: `npm run demo`, then wait for the camera.")
        return
    if label not in ROOM_ACTIVITY_LABELS:
        await reply(f"Unknown label {label!r}. Use: {', '.join(ROOM_ACTIVITY_LABELS)}")
        return

    await reply("📸 Capturing the live webcam frame and teaching Haven…")

    try:
        result = await asyncio.to_thread(
            state.engine.record_feedback,
            corrected_label=label,
            notes=notes,
            metadata={"source": "telegram", "telegram_chat_id": chat_id},
        )
    except ValueError as e:
        await reply(f"Could not save: {e}")
        return
    except RuntimeError as e:
        await reply(f"Could not save: {e}")
        return

    event = publish_feedback_result(result, source="telegram", notes=notes)
    correction = result["correction"]
    auto = state.engine.auto_retrain_status() if state.engine else {}
    confirmed = correction.predicted_label == correction.corrected_label

    lines = [
        "✅ *Haven updated from Telegram*",
        "",
        f"*You said:* {notes[:200]}",
        f"*Saved as:* {correction.corrected_label}",
        f"*Model thought:* {correction.predicted_label} ({correction.confidence:.0%})",
        f"*Screenshot + features stored* ({len(correction.screenshot_paths)} frame(s))",
        f"*Room memory:* {result.get('memory_examples', 0)} examples",
    ]
    if confirmed:
        lines.append("_Confirmed the current read._")
    else:
        lines.append("_Wrong read corrected — similar scenes should shift._")
    if auto.get("enabled"):
        lines.append("_🔄 Auto-retrain queued on this exact snapshot._")
    lines.append("")
    lines.append("_Check your Haven /live page — a banner should appear now._")

    await reply("\n".join(lines), parse_mode="Markdown")

    msg = reply_message
    if msg is None:
        return
    cap = f"Haven snapshot → {correction.corrected_label}"
    try:
        await _send_correction_photo(msg, event.correction_id, cap)
    except Exception:
        log.debug("Could not send Telegram photo for correction %s", event.correction_id, exc_info=True)


async def start_telegram_bot() -> None:
    global _application
    if not _telegram_ready():
        if settings.telegram_enabled:
            log.warning("TELEGRAM_ENABLED=1 but token or TELEGRAM_ALLOWED_CHAT_IDS missing — bot not started.")
        return

    token = settings.telegram_bot_token.strip()
    allowed = parse_allowed_chat_ids(settings.telegram_allowed_chat_ids)
    bot_id = bot_user_id_from_token(token)
    if bot_id is not None and bot_id in allowed:
        log.error(
            "TELEGRAM_ALLOWED_CHAT_IDS includes the bot id (%s). Use YOUR user id from @userinfobot.",
            bot_id,
        )

    from telegram import Update
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

    async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None or not _allowed(update.effective_chat.id):
            return
        await update.message.reply_text(
            "*Haven* — control your room from Telegram.\n\n"
            "*Activity correction:*\n"
            "_I'm not sleeping, I'm working_\n"
            "→ captures webcam + retrains\n\n"
            "*Preferences:*\n"
            "_Turn the fan lower for work_\n"
            "_Change the light to blue_\n"
            "→ saves to your Haven preferences\n\n"
            "Or tap a label below. Requires `npm run demo` on the same machine.",
            reply_markup=_label_keyboard(),
            parse_mode="Markdown",
        )

    async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None or not _allowed(update.effective_chat.id):
            return
        await update.message.reply_text(
            "Activity: " + ", ".join(ROOM_ACTIVITY_LABELS) + "\n"
            "Preferences: fan, light color, brightness, temperature\n\n"
            "Examples:\n"
            "`not sleeping — working`\n"
            "`dim the lights for relaxing`",
            reply_markup=_label_keyboard(),
            parse_mode="Markdown",
        )

    async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None or not _allowed(update.effective_chat.id):
            return
        if state.engine is None:
            await update.message.reply_text("Haven engine: off. Run `npm run demo`.")
            return
        snap = state.hub.latest
        fb = state.engine.feedback_status()
        if snap is None:
            await update.message.reply_text(
                f"Engine: {state.live_mode}, waiting for first snapshot…\n"
                f"Feedback memory: {fb.get('memory_examples', 0)} examples."
            )
            return
        await update.message.reply_text(
            f"Haven mode: {state.live_mode}\n"
            f"Now: *{snap.primary_state}* ({snap.primary_confidence:.0%})\n"
            f"Memory: {fb.get('memory_examples', 0)} examples",
            parse_mode="Markdown",
        )

    async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None or query.message is None:
            return
        chat_id = query.message.chat_id
        if not _allowed(chat_id):
            await query.answer("Unauthorized", show_alert=True)
            return
        data = query.data or ""
        if not data.startswith("label:"):
            await query.answer()
            return
        label = data.split(":", 1)[1]
        await query.answer(f"Teaching Haven: {label}…")

        async def reply(text: str, **kwargs: Any) -> None:
            await query.message.reply_text(text, **kwargs)

        await _apply_label(
            chat_id=chat_id,
            label=label,
            notes=f"telegram button: {label}",
            reply=reply,
            reply_message=query.message,
        )

    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None or update.message is None or not update.message.text:
            return
        if not _allowed(update.effective_chat.id):
            return
        text = update.message.text.strip()
        if text.startswith("/"):
            return

        chat_id = update.effective_chat.id
        status_msg = await update.message.reply_text("🧠 Reading your message (OpenAI)…")

        async def reply(msg: str, **kwargs: Any) -> None:
            await status_msg.edit_text(msg, **kwargs)

        predicted = _predicted_label()

        try:
            doc = await asyncio.to_thread(load_preferences)
            active_id = resolve_active_preset_id(doc)
            preset = next(
                (p for p in doc.get("presets", []) if isinstance(p, dict) and str(p.get("id")) == active_id),
                None,
            )
            preset_name = str(preset.get("name", active_id)) if isinstance(preset, dict) else active_id
            pref_parsed = await parse_preference_text(
                text,
                current_state=predicted,
                active_preset_name=preset_name,
                api_key=settings.openai_api_key,
                model=settings.openai_model,
            )
        except Exception as e:
            log.exception("Preference parse failed")
            pref_parsed = None

        if pref_parsed and pref_parsed.applies:
            if pref_parsed.needs_clarification:
                await reply(pref_parsed.clarification_question)
                return
            if pref_parsed.spec is None:
                await reply("Which preference should I change? Fan, light, brightness, or temperature?")
                return
            try:
                result = await asyncio.to_thread(
                    apply_and_save_preferences,
                    pref_parsed.spec,
                    source="telegram",
                    notes=text,
                    fallback_state=predicted,
                )
            except PreferenceValidationError as e:
                await reply(f"Could not update preferences: {e}")
                return
            state_lines = "\n".join(f"• {c}" for c in result.changes)
            await reply(
                "⚙️ *Haven preferences saved*\n\n"
                f"*Preset:* {result.preset_name}\n"
                f"*Moods:* {', '.join(result.target_states)}\n\n"
                f"{state_lines}\n\n"
                "_Open /preferences on Haven to see the update._",
                parse_mode="Markdown",
            )
            return

        try:
            parsed: TelegramLabelParse = await parse_correction_text(
                text,
                predicted_label=predicted,
                api_key=settings.openai_api_key,
                model=settings.openai_model,
            )
        except Exception as e:
            log.exception("OpenAI parse failed")
            await reply(
                f"Could not understand that ({e}).\nTap a label or say: work, sleep, gaming, relaxing, away.",
                reply_markup=_label_keyboard(),
            )
            return

        if parsed.needs_clarification:
            await reply(parsed.clarification_question, reply_markup=_label_keyboard())
            return

        await _apply_label(
            chat_id=chat_id,
            label=parsed.corrected_label,
            notes=text,
            reply=reply,
            reply_message=update.message,
        )

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    _application = app
    log.info("Haven Telegram bot polling (allowed chats: %s)", sorted(allowed))


async def stop_telegram_bot() -> None:
    global _application
    app = _application
    _application = None
    if app is None:
        return
    try:
        if app.updater.running:
            await app.updater.stop()
        await app.stop()
        await app.shutdown()
    except Exception:
        log.exception("Telegram bot shutdown error")
    log.info("Telegram bot stopped")
