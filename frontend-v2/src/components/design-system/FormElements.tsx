import {
  createContext,
  useContext,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react'
import { ChevronDownIcon } from '../icons'

const FormFieldContext = createContext<string>('')

interface FormFieldProps {
  id?: string
  label: string
  required?: boolean
  error?: string
  helperText?: string
  children: ReactNode
  className?: string
}

export function FormField({
  id: propId,
  label,
  required = false,
  error,
  helperText,
  children,
  className = '',
}: FormFieldProps) {
  const generatedId = useId()
  const id = propId || generatedId
  return (
    <FormFieldContext.Provider value={id}>
      <div className={`space-y-1.5 ${className}`}>
        <label htmlFor={id} className="block text-xs font-bold uppercase tracking-wider text-slate-700">
          {label}
          {required && (
            <span className="ml-1 text-rose-500 font-bold" title="Required field" aria-hidden="true">
              *
            </span>
          )}
        </label>
        {children}
        {error && (
          <p id={`${id}-error`} className="text-xs font-medium text-rose-600 animate-in fade-in" role="alert">
            {error}
          </p>
        )}
        {!error && helperText && (
          <p id={`${id}-helper`} className="text-xs text-slate-500">
            {helperText}
          </p>
        )}
      </div>
    </FormFieldContext.Provider>
  )
}

interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: boolean
  icon?: ReactNode
}

export function TextInput({ error, icon, className = '', id: propId, ...props }: TextInputProps) {
  const contextId = useContext(FormFieldContext)
  const id = propId || contextId || undefined
  const borderClasses = error
    ? 'border-rose-300 focus:border-rose-500 focus:ring-rose-100'
    : 'border-slate-300 focus:border-cyan-600 focus:ring-cyan-100 hover:border-slate-400'

  return (
    <div className="relative">
      {icon && (
        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-slate-400">
          {icon}
        </div>
      )}
      <input
        id={id}
        className={`block w-full rounded-xl border bg-white px-3.5 py-2.5 text-sm text-slate-900 shadow-xs transition placeholder:text-slate-400 focus:outline-hidden focus:ring-3 ${
          icon ? 'pl-10' : ''
        } ${borderClasses} ${className}`}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={error && id ? `${id}-error` : undefined}
        {...props}
      />
    </div>
  )
}

interface SelectInputProps extends SelectHTMLAttributes<HTMLSelectElement> {
  error?: boolean
  options?: Array<{ value: string; label: string }>
}

export function SelectInput({
  error,
  options,
  children,
  className = '',
  id: propId,
  ...props
}: SelectInputProps) {
  const contextId = useContext(FormFieldContext)
  const id = propId || contextId || undefined
  const borderClasses = error
    ? 'border-rose-300 focus:border-rose-500 focus:ring-rose-100'
    : 'border-slate-300 focus:border-cyan-600 focus:ring-cyan-100 hover:border-slate-400'

  return (
    <div className="relative">
      <select
        id={id}
        className={`block w-full appearance-none rounded-xl border bg-white px-3.5 py-2.5 pr-10 text-sm text-slate-900 shadow-xs transition focus:outline-hidden focus:ring-3 ${borderClasses} ${className}`}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={error && id ? `${id}-error` : undefined}
        {...props}
      >
        {options
          ? options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))
          : children}
      </select>
      <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400">
        <ChevronDownIcon className="h-4 w-4" />
      </div>
    </div>
  )
}

interface TextareaInputProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: boolean
}

export function TextareaInput({ error, className = '', id: propId, ...props }: TextareaInputProps) {
  const contextId = useContext(FormFieldContext)
  const id = propId || contextId || undefined
  const borderClasses = error
    ? 'border-rose-300 focus:border-rose-500 focus:ring-rose-100'
    : 'border-slate-300 focus:border-cyan-600 focus:ring-cyan-100 hover:border-slate-400'

  return (
    <textarea
      id={id}
      rows={props.rows ?? 3}
      className={`block w-full rounded-xl border bg-white px-3.5 py-2.5 text-sm text-slate-900 shadow-xs transition placeholder:text-slate-400 focus:outline-hidden focus:ring-3 ${borderClasses} ${className}`}
      aria-invalid={error ? 'true' : undefined}
      aria-describedby={error && id ? `${id}-error` : undefined}
      {...props}
    />
  )
}
