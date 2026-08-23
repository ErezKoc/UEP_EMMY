import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  cancelAppointment,
  getAppointments,
  respondToAppointment,
} from "../../api/client";
import { useSession } from "../../auth/SessionContext";
import ClinicContact from "../../components/ClinicContact";
import {
  Badge,
  Button,
  CalendarIcon,
  EmptyState,
  Input,
  Modal,
  Spinner,
  StethoscopeIcon,
  Textarea,
  useToast,
} from "../../components/ui";
import { capitalize, formatDate } from "../../lib/format";
import type { Appointment, AppointmentStatus } from "../../types";

const STATUS_LABEL: Record<AppointmentStatus, string> = {
  requested: "Waiting for the practice",
  confirmed: "Confirmed",
  declined: "Declined",
  cancelled: "Cancelled",
};

const STATUS_VARIANT: Record<AppointmentStatus, "primary" | "success" | "neutral" | "danger"> = {
  requested: "primary",
  confirmed: "success",
  declined: "danger",
  cancelled: "neutral",
};

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

  const load = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      setAppointments(await getAppointments());
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Could not load appointments.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const waiting = appointments.filter((item) => item.status === "requested");
  const settled = appointments.filter((item) => item.status !== "requested");

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
          <button onClick={() => void load()} className="font-medium underline">
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

      {waiting.length > 0 && (
        <section className="mt-8">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Waiting for a reply ({waiting.length})
          </h2>
          <ul className="mt-3 space-y-4">
            {waiting.map((appointment) => (
              <AppointmentRow
                key={appointment.id}
                appointment={appointment}
                viewerId={user?.id ?? ""}
                onChanged={load}
              />
            ))}
          </ul>
        </section>
      )}

      {settled.length > 0 && (
        <section className="mt-8">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Answered
          </h2>
          <ul className="mt-3 space-y-4">
            {settled.map((appointment) => (
              <AppointmentRow
                key={appointment.id}
                appointment={appointment}
                viewerId={user?.id ?? ""}
                onChanged={load}
              />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function AppointmentRow({
  appointment,
  viewerId,
  onChanged,
}: {
  appointment: Appointment;
  viewerId: string;
  onChanged: () => void;
}) {
  const { toast } = useToast();
  const [replyOpen, setReplyOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  // Which side of this appointment is reading it. An account can be both the
  // owner on one row and the practice on another, so this is per row.
  const isPractice = appointment.vet.id === viewerId;
  const other = isPractice ? appointment.owner : appointment.vet;
  const practiceName = appointment.vet.clinic_name ?? appointment.vet.display_name;
  const movedDay =
    appointment.status === "confirmed" &&
    appointment.scheduled_date !== null &&
    appointment.scheduled_date !== appointment.preferred_date;

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
            {formatDate(appointment.preferred_date)}
            {appointment.preferred_time_note ? ` — ${appointment.preferred_time_note}` : ""}
          </dd>
        </div>
        {appointment.scheduled_date && (
          <div className="flex flex-wrap gap-x-2">
            <dt className="font-medium text-slate-600">Confirmed for:</dt>
            <dd className={movedDay ? "font-semibold text-amber-800" : "text-slate-800"}>
              {formatDate(appointment.scheduled_date)}
              {/*
                Said in words, not just by the dates differing. Someone
                skim-reading two dates a line apart will take the second for a
                restatement of the first and turn up on the wrong day.
              */}
              {movedDay && " — a different day from the one you asked for"}
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

      {/* The owner gets the practice's details on a confirmed row: the number
          to ring on the day belongs next to the appointment, not one page away. */}
      {!isPractice && appointment.status === "confirmed" && <ClinicContact vet={appointment.vet} />}

      <div className="mt-4 flex flex-wrap gap-2">
        {isPractice && appointment.status === "requested" && (
          <Button size="sm" onClick={() => setReplyOpen(true)}>
            Answer this request
          </Button>
        )}
        {(appointment.status === "requested" || appointment.status === "confirmed") && (
          <Button size="sm" variant="secondary" onClick={() => void cancel()} disabled={busy}>
            {appointment.status === "confirmed" ? "Cancel appointment" : "Withdraw request"}
          </Button>
        )}
      </div>

      {isPractice && (
        <ReplyDialog
          appointment={appointment}
          open={replyOpen}
          onClose={() => setReplyOpen(false)}
          onAnswered={onChanged}
        />
      )}
    </li>
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
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const answer = async (confirm: boolean) => {
    setBusy(true);
    setError(null);
    try {
      await respondToAppointment(appointment.id, {
        confirm,
        scheduled_date: confirm ? scheduledDate : null,
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
          {appointment.owner.display_name} asked for {formatDate(appointment.preferred_date)}
          {appointment.preferred_time_note ? ` (${appointment.preferred_time_note})` : ""}.
        </p>

        <Input
          label="Confirm for"
          type="date"
          value={scheduledDate}
          onChange={(event) => setScheduledDate(event.target.value)}
          hint="Change this to offer a different day. The owner sees both dates."
        />

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
