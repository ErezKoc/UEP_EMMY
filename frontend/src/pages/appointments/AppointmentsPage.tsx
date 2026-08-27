import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  cancelAppointment,
  getAppointmentMessages,
  getAppointments,
  proposeReschedule,
  addAppointmentNote,
  respondToAppointment,
  respondToReschedule,
  sendAppointmentMessage,
} from "../../api/client";
import { useSession } from "../../auth/SessionContext";
import ClinicContact from "../../components/ClinicContact";
import {
  Avatar,
  Badge,
  Button,
  CalendarIcon,
  ChatIcon,
  ClockIcon,
  EmptyState,
  Input,
  Modal,
  SendIcon,
  Spinner,
  StethoscopeIcon,
  Textarea,
  useToast,
} from "../../components/ui";
import { capitalize, formatDate, formatRelativeTime, formatWhen } from "../../lib/format";
import type { Appointment, AppointmentMessage, AppointmentStatus } from "../../types";

const STATUS_LABEL: Record<AppointmentStatus, string> = {
  requested: "Waiting for the practice",
  confirmed: "Confirmed",
  reschedule_proposed: "New time suggested",
  declined: "Declined",
  cancelled: "Cancelled",
};

const STATUS_VARIANT: Record<AppointmentStatus, "primary" | "success" | "neutral" | "danger"> = {
  requested: "primary",
  confirmed: "success",
  // Not "danger": nothing has gone wrong and nothing has been lost. There is a
  // standing appointment underneath and a question waiting on top of it.
  reschedule_proposed: "primary",
  declined: "danger",
  cancelled: "neutral",
};

/** Today in the browser's own timezone, for a date input's floor. */
function todayValue(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

/** "14:30:00" -> "14:30", which is what an `<input type="time">` wants. */
function timeInputValue(clock: string | null): string {
  return clock ? clock.slice(0, 5) : "";
}

/*
 * One page, both sides.
 *
 * Not /my-appointments and /appointment-requests. A veterinarian owns pets too,
 * and splitting the list by role would hide one of their two lists behind a URL
 * they have no reason to visit. Each row knows which side the viewer is on and
 * shows the controls that side has.
 */
export default function AppointmentsPage() {
  const { user } = useSession();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  /*
   * `quiet` skips the spinner, and exists because of what the spinner does to
   * the page: it replaces the whole list, which unmounts every row and takes
   * the open message thread with it. Sending a message closed the conversation
   * you were having, mid-conversation.
   *
   * A quiet refresh swaps the data underneath the same rows - the keys are
   * stable - so the counts update and the thread stays open and scrolled where
   * it was.
   */
  const load = useCallback(async (quiet = false) => {
    if (!quiet) setIsLoading(true);
    setLoadError(null);
    try {
      setAppointments(await getAppointments());
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Could not load appointments.");
    } finally {
      if (!quiet) setIsLoading(false);
    }
  }, []);

  const refresh = useCallback(() => void load(), [load]);
  const refreshQuietly = useCallback(() => void load(true), [load]);

  useEffect(() => {
    void load();
  }, [load]);

  /*
   * "Needs you" rather than "requested".
   *
   * A suggested new time is waiting on somebody exactly as much as an
   * unanswered request is, and it is waiting on whichever side did NOT suggest
   * it — which the server cannot sort by, because it depends on who is
   * reading. Leaving these down in "Answered" is how a question sits for three
   * days: the section heading said it had been dealt with.
   */
  const needsYou = appointments.filter(
    (item) =>
      (item.status === "requested" && item.vet.id === user?.id) ||
      (item.status === "reschedule_proposed" && item.proposed_by_id !== user?.id),
  );
  const waiting = appointments.filter(
    (item) =>
      !needsYou.includes(item) &&
      (item.status === "requested" || item.status === "reschedule_proposed"),
  );
  const settled = appointments.filter(
    (item) => item.status !== "requested" && item.status !== "reschedule_proposed",
  );

  const sections: Array<{ title: string; items: Appointment[] }> = [
    { title: `Needs your answer (${needsYou.length})`, items: needsYou },
    { title: `Waiting on the other side (${waiting.length})`, items: waiting },
    { title: "Answered", items: settled },
  ];

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-bold text-slate-800">Appointments</h1>
      <p className="mt-1 text-sm text-slate-500">
        Requests you have sent to a practice, and requests sent to you.
      </p>

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      )}

      {!isLoading && loadError && (
        <div className="mt-6 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
          {loadError}{" "}
          <button onClick={refresh} className="font-medium underline">
            Retry
          </button>
        </div>
      )}

      {!isLoading && !loadError && appointments.length === 0 && (
        <div className="mt-6">
          <EmptyState
            icon={<CalendarIcon className="h-6 w-6" />}
            title="No appointments yet"
            description="Find a practice in the directory and send them a request."
            action={
              <Link to="/vets">
                <Button variant="secondary">
                  <StethoscopeIcon className="h-4 w-4" />
                  Find a vet
                </Button>
              </Link>
            }
          />
        </div>
      )}

      {!isLoading &&
        !loadError &&
        sections
          .filter((section) => section.items.length > 0)
          .map((section) => (
            <section key={section.title} className="mt-8">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                {section.title}
              </h2>
              <ul className="mt-3 space-y-4">
                {section.items.map((appointment) => (
                  <AppointmentRow
                    key={appointment.id}
                    appointment={appointment}
                    viewerId={user?.id ?? ""}
                    onChanged={refresh}
                    onMessaged={refreshQuietly}
                  />
                ))}
              </ul>
            </section>
          ))}
    </div>
  );
}

function AppointmentRow({
  appointment,
  viewerId,
  onChanged,
  onMessaged,
}: {
  appointment: Appointment;
  viewerId: string;
  onChanged: () => void;
  /** Refresh without the spinner, so an open thread is not torn down. */
  onMessaged: () => void;
}) {
  const { toast } = useToast();
  const [replyOpen, setReplyOpen] = useState(false);
  const [moveOpen, setMoveOpen] = useState(false);
  const [noteOpen, setNoteOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  // Which side of this appointment is reading it. An account can be both the
  // owner on one row and the practice on another, so this is per row.
  const isPractice = appointment.vet.id === viewerId;
  const other = isPractice ? appointment.owner : appointment.vet;
  const practiceName = appointment.vet.clinic_name ?? appointment.vet.display_name;
  const movedDay =
    appointment.scheduled_date !== null &&
    appointment.scheduled_date !== appointment.preferred_date;
  const pendingMove = appointment.status === "reschedule_proposed";
  const iProposed = appointment.proposed_by_id === viewerId;
  const canMove = appointment.status === "confirmed";

  const cancel = async () => {
    setBusy(true);
    try {
      await cancelAppointment(appointment.id);
      toast("Appointment cancelled.", "success");
      onChanged();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not cancel.", "error");
    } finally {
      setBusy(false);
    }
  };

  const answerMove = async (accept: boolean) => {
    setBusy(true);
    try {
      await respondToReschedule(appointment.id, { accept });
      toast(accept ? "Appointment moved." : "New time turned down.", "success");
      onChanged();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not answer.", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={STATUS_VARIANT[appointment.status]}>
          {STATUS_LABEL[appointment.status]}
        </Badge>
        <span className="font-semibold text-slate-800">
          {isPractice ? other.display_name : practiceName}
        </span>
        {appointment.animal && (
          <span className="text-sm text-slate-500">
            for {appointment.animal.name} ({capitalize(appointment.animal.species)})
          </span>
        )}
      </div>

      <dl className="mt-3 space-y-1 text-sm">
        <div className="flex flex-wrap gap-x-2">
          <dt className="font-medium text-slate-600">Asked for:</dt>
          <dd className="text-slate-800">
            {appointment.preferred_time
              ? formatWhen(appointment.preferred_date, appointment.preferred_time)
              : /*
                  Said out loud rather than left as a bare date, so the practice
                  can tell "any time is fine" apart from "they forgot to say".
                */
                `${formatDate(appointment.preferred_date)} — no particular time`}
            {appointment.preferred_time_note ? ` (${appointment.preferred_time_note})` : ""}
          </dd>
        </div>
        {appointment.scheduled_date && (
          <div className="flex flex-wrap gap-x-2">
            <dt className="font-medium text-slate-600">
              {pendingMove ? "Currently booked for:" : "Confirmed for:"}
            </dt>
            <dd className={movedDay ? "font-semibold text-amber-800" : "font-semibold text-slate-800"}>
              {formatWhen(appointment.scheduled_date, appointment.scheduled_time)}
              {/*
                Said in words, not just by the dates differing. Someone
                skim-reading two dates a line apart will take the second for a
                restatement of the first and turn up on the wrong day.
              */}
              {/* Whose "you" this is depends on which side is reading. */}
              {movedDay &&
                (isPractice
                  ? " — a different day from the one they asked for"
                  : " — a different day from the one you asked for")}
              {/*
                Only ever true for a row confirmed before exact times existed.
                Named rather than left blank, because a missing time on a
                confirmed appointment is the exact problem this feature fixes
                and the owner should know to ring rather than guess.
              */}
              {!appointment.scheduled_time && (
                <span className="ml-1 font-normal text-slate-500">
                  — no time was given; ring the practice to check
                </span>
              )}
            </dd>
          </div>
        )}
      </dl>

      <p className="mt-3 whitespace-pre-wrap text-sm text-slate-700">{appointment.reason}</p>

      {appointment.vet_note && (
        <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
          <span className="font-medium">From the practice: </span>
          {appointment.vet_note}
        </p>
      )}

      {/*
        The proposal, kept visually apart from the booking above it. Both are
        true at once — there is an appointment to turn up to AND a question
        about moving it — and merging them into one line is how somebody ends up
        acting on a time nobody agreed to.
      */}
      {pendingMove && appointment.proposed_date && (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-sm">
          <p className="font-semibold text-amber-900">
            <ClockIcon className="mr-1 inline h-4 w-4" />
            {iProposed ? "You suggested" : `${other.display_name} suggested`}{" "}
            {formatWhen(appointment.proposed_date, appointment.proposed_time)}
          </p>
          {appointment.proposed_note && (
            <p className="mt-1 text-amber-900/80">{appointment.proposed_note}</p>
          )}
          <p className="mt-1 text-xs text-amber-900/70">
            Nothing has moved yet. The appointment above still stands until this is answered.
          </p>
          {!iProposed && (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button size="sm" onClick={() => void answerMove(true)} disabled={busy}>
                Accept the new time
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => void answerMove(false)}
                disabled={busy}
              >
                Keep the original
              </Button>
            </div>
          )}
        </div>
      )}

      {/* The owner gets the practice's details on a confirmed row: the number
          to ring on the day belongs next to the appointment, not one page away. */}
      {!isPractice && (appointment.status === "confirmed" || pendingMove) && (
        <ClinicContact vet={appointment.vet} />
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {isPractice && appointment.status === "requested" && (
          <Button size="sm" onClick={() => setReplyOpen(true)}>
            Answer this request
          </Button>
        )}
        {canMove && (
          <Button size="sm" variant="secondary" onClick={() => setMoveOpen(true)}>
            <ClockIcon className="h-4 w-4" />
            Suggest a new time
          </Button>
        )}
        {/*
          Adding to the record after the answer has gone. The note on the
          answer dialog can only ever be written at the moment of answering,
          which left "bring the previous blood results" and "the swelling has
          gone down" with nowhere to go but the message thread - a conversation
          rather than something the owner can come back to. It lands in their
          calendar entry and their inbox.
        */}
        {isPractice && appointment.status !== "requested" && (
          <Button size="sm" variant="secondary" onClick={() => setNoteOpen(true)}>
            {appointment.vet_note ? "Edit your note" : "Add a note"}
          </Button>
        )}
        {appointment.status !== "cancelled" && appointment.status !== "declined" && (
          <Button size="sm" variant="ghost" onClick={() => void cancel()} disabled={busy}>
            {appointment.status !== "requested"
              ? "Cancel appointment"
              : /* The practice is not withdrawing anything - it is somebody
                   else's request, and their word for dropping it is different. */
                isPractice
                ? "Close without answering"
                : "Withdraw request"}
          </Button>
        )}
      </div>

      <MessageThread
        appointment={appointment}
        viewerId={viewerId}
        otherLabel={isPractice ? "the owner" : "the practice"}
        onSent={onMessaged}
      />

      {isPractice && (
        <>
          <ReplyDialog
            appointment={appointment}
            open={replyOpen}
            onClose={() => setReplyOpen(false)}
            onAnswered={onChanged}
          />
          <VetNoteDialog
            appointment={appointment}
            open={noteOpen}
            onClose={() => setNoteOpen(false)}
            onSaved={onChanged}
          />
        </>
      )}
      <RescheduleDialog
        appointment={appointment}
        open={moveOpen}
        onClose={() => setMoveOpen(false)}
        onProposed={onChanged}
      />
    </li>
  );
}

/*
 * The conversation, on the appointment it is about.
 *
 * Collapsed by default and fetched only when opened. A page of appointments
 * that eagerly loaded every thread would fire one request per row to render
 * text nobody has asked to see — and the unread count needed for the button is
 * already on the appointment itself, so the closed state costs nothing.
 */
function MessageThread({
  appointment,
  viewerId,
  otherLabel,
  onSent,
}: {
  appointment: Appointment;
  viewerId: string;
  /** "the practice" or "the owner" - whoever is on the far side of this row. */
  otherLabel: string;
  onSent: () => void;
}) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<AppointmentMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  const unread = appointment.unread_message_count;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setMessages(await getAppointmentMessages(appointment.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load the messages.");
    } finally {
      setLoading(false);
    }
  }, [appointment.id]);

  useEffect(() => {
    if (!open) return;
    void load();
  }, [open, load]);

  useEffect(() => {
    if (open && messages.length > 0) endRef.current?.scrollIntoView({ block: "nearest" });
  }, [open, messages.length]);

  const send = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const body = draft.trim();
    if (!body) return;
    setSending(true);
    setError(null);
    try {
      const created = await sendAppointmentMessage(appointment.id, body);
      setMessages((current) => [...current, created]);
      setDraft("");
      // The row's counters live on the appointment, so the list needs telling.
      onSent();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send that.");
      toast("Message not sent.", "error");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="mt-4 border-t border-slate-100 pt-3">
      <button
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex items-center gap-2 text-sm font-medium text-primary-600 hover:text-primary-700"
      >
        <ChatIcon className="h-4 w-4" />
        {appointment.message_count === 0
          ? `Message ${otherLabel}`
          : `Messages (${appointment.message_count})`}
        {/*
          The count is on the collapsed control, because that is the only thing
          a reader scanning the page sees. An unread badge inside a panel nobody
          has opened tells nobody anything.
        */}
        {unread > 0 && (
          <span className="rounded-full bg-rose-600 px-2 py-0.5 text-xs font-semibold text-white">
            {unread} new
          </span>
        )}
      </button>

      {open && (
        <div className="mt-3">
          {loading && (
            <div className="flex justify-center py-6">
              <Spinner />
            </div>
          )}

          {!loading && messages.length === 0 && (
            <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-500">
              Nothing yet. Anything you write here stays attached to this appointment, so both
              of you can find it later.
            </p>
          )}

          <ul className="max-h-72 space-y-3 overflow-y-auto">
            {messages.map((message) => {
              const mine = message.sender.id === viewerId;
              return (
                <li key={message.id} className={`flex gap-2 ${mine ? "flex-row-reverse" : ""}`}>
                  <Avatar
                    name={message.sender.display_name}
                    src={message.sender.avatar_url}
                    size="sm"
                  />
                  <div className={`max-w-[80%] ${mine ? "text-right" : ""}`}>
                    <div
                      className={`inline-block rounded-2xl px-3 py-2 text-sm ${
                        mine
                          ? "bg-primary-600 text-white"
                          : "bg-slate-100 text-slate-800"
                      }`}
                    >
                      <p className="whitespace-pre-wrap text-left">{message.body}</p>
                    </div>
                    <p className="mt-0.5 text-xs text-slate-400">
                      {mine ? "You" : message.sender.display_name} ·{" "}
                      {formatRelativeTime(message.created_at)}
                    </p>
                  </div>
                </li>
              );
            })}
            <div ref={endRef} />
          </ul>

          <form onSubmit={send} className="mt-3 flex items-end gap-2">
            <div className="flex-1">
              <label htmlFor={`msg-${appointment.id}`} className="sr-only">
                Message
              </label>
              <textarea
                id={`msg-${appointment.id}`}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                rows={2}
                maxLength={2000}
                placeholder="Is he still limping? Anything we should bring?"
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-100"
              />
            </div>
            <Button type="submit" size="sm" loading={sending} disabled={!draft.trim()}>
              <SendIcon className="h-4 w-4" />
              Send
            </Button>
          </form>

          {error && (
            <p className="mt-2 text-sm text-rose-600" role="alert">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function ReplyDialog({
  appointment,
  open,
  onClose,
  onAnswered,
}: {
  appointment: Appointment;
  open: boolean;
  onClose: () => void;
  onAnswered: () => void;
}) {
  const { toast } = useToast();
  const [scheduledDate, setScheduledDate] = useState(appointment.preferred_date);
  /*
   * Seeded with whatever the owner asked for, and empty when they had no
   * preference. Not defaulted to 09:00 or to now: a time already sitting in the
   * box is a time that gets confirmed by a practice that meant to change it,
   * and the owner has no way to tell that apart from a deliberate answer.
   */
  const [scheduledTime, setScheduledTime] = useState(
    timeInputValue(appointment.preferred_time),
  );
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const answer = async (confirm: boolean) => {
    // Checked here as well as on the server so the practice is told what is
    // missing before a round trip, and told it next to the field.
    if (confirm && !scheduledTime) {
      setError("Give the exact time you are confirming, so the owner knows when to arrive.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await respondToAppointment(appointment.id, {
        confirm,
        scheduled_date: confirm ? scheduledDate : null,
        scheduled_time: confirm ? scheduledTime : null,
        vet_note: note.trim() || null,
      });
      toast(confirm ? "Appointment confirmed." : "Request declined.", "success");
      onAnswered();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send the answer.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Answer this request"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Close
          </Button>
          <Button variant="secondary" onClick={() => void answer(false)} disabled={busy}>
            Decline
          </Button>
          <Button onClick={() => void answer(true)} loading={busy}>
            Confirm
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          {appointment.owner.display_name} asked for{" "}
          {appointment.preferred_time
            ? formatWhen(appointment.preferred_date, appointment.preferred_time)
            : `${formatDate(appointment.preferred_date)}, with no particular time`}
          {appointment.preferred_time_note ? ` (${appointment.preferred_time_note})` : ""}.
        </p>

        <div className="grid gap-3 sm:grid-cols-2">
          <Input
            label="Confirm for"
            type="date"
            value={scheduledDate}
            onChange={(event) => setScheduledDate(event.target.value)}
            hint="Change this to offer a different day. The owner sees both dates."
          />
          <Input
            label="At"
            type="time"
            value={scheduledTime}
            onChange={(event) => setScheduledTime(event.target.value)}
            required
            hint="Required to confirm — this is the time the owner will turn up."
          />
        </div>

        <Textarea
          label="Note to the owner (optional)"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Please bring any previous test results. If declining, a short reason helps."
          rows={3}
          maxLength={1000}
        />

        {error && (
          <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}

/*
 * What the practice wrote down about the visit.
 *
 * Replaces the note rather than appending to it, and re-announces on every
 * change. A correction to clinical wording is the message most worth
 * delivering, so an edit is news rather than noise - and the owner reading it
 * later needs one current note, not a thread of superseded ones.
 */
function VetNoteDialog({
  appointment,
  open,
  onClose,
  onSaved,
}: {
  appointment: Appointment;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { toast } = useToast();
  const [note, setNote] = useState(appointment.vet_note ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    if (!note.trim()) {
      setError("Write the note first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await addAppointmentNote(appointment.id, note.trim());
      toast("Note saved. The owner has been told.", "success");
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the note.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={appointment.vet_note ? "Edit your note" : "Add a note"}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Close
          </Button>
          <Button onClick={() => void save()} loading={busy}>
            Save and notify
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          {appointment.owner.display_name} will see this on the appointment, in their calendar
          entry, and by email if they have email switched on.
        </p>
        <Textarea
          label="Note"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="What you would like the owner to know or to bring."
          rows={4}
          maxLength={1000}
          hint="Keep it to what the owner needs. This is a record of what was said, not a diagnosis."
        />
        {error && (
          <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}


/*
 * Suggesting a different time for something already agreed.
 *
 * Open to both sides, and the wording is "suggest" everywhere because that is
 * all it is until the other party answers. Until this existed the only way to
 * move an appointment was to cancel it and start again from an empty form,
 * which threw away the reason, the pet, the thread and the practice's answer —
 * and left a gap in which neither side had an appointment at all.
 */
function RescheduleDialog({
  appointment,
  open,
  onClose,
  onProposed,
}: {
  appointment: Appointment;
  open: boolean;
  onClose: () => void;
  onProposed: () => void;
}) {
  const { toast } = useToast();
  const [newDate, setNewDate] = useState(appointment.scheduled_date ?? todayValue());
  const [newTime, setNewTime] = useState(timeInputValue(appointment.scheduled_time));
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!newDate || !newTime) {
      setError("Pick both a day and a time.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await proposeReschedule(appointment.id, {
        new_date: newDate,
        new_time: newTime,
        note: note.trim() || null,
      });
      toast("Suggested. The other side will answer.", "success");
      setNote("");
      onProposed();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not suggest that time.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Suggest a new time"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={() => void submit()} loading={busy}>
            Send suggestion
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
          The appointment stays as it is —{" "}
          <span className="font-medium text-slate-800">
            {appointment.scheduled_date
              ? formatWhen(appointment.scheduled_date, appointment.scheduled_time)
              : "as booked"}
          </span>{" "}
          — until the other side accepts. Nothing moves on anyone&apos;s calendar before then.
        </p>

        <div className="grid gap-3 sm:grid-cols-2">
          <Input
            label="New day"
            type="date"
            value={newDate}
            min={todayValue()}
            onChange={(event) => setNewDate(event.target.value)}
            required
          />
          <Input
            label="New time"
            type="time"
            value={newTime}
            onChange={(event) => setNewTime(event.target.value)}
            required
          />
        </div>

        <Textarea
          label="Why? (optional)"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Our morning list has overrun — could we move you to the afternoon?"
          rows={3}
          maxLength={1000}
        />

        {error && (
          <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}
