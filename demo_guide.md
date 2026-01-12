# Demo Guide and Observations

This guide explains how to run the demos and what to observe when comparing the
**event-driven streaming model** against the **HTTP polling baseline**.

The demos are designed to surface **delivery behavior, latency, and system cost tradeoffs**
rather than to optimize for a specific workload.

---

## General Demo Flow

Both demos follow the same interaction pattern:

1. Start the full system using Docker Compose.
2. Open the Demo Hub UI in a browser.
3. Run the task in both **streaming** and **polling** modes.
4. Observe metrics and client-side behavior while the task is running.

For meaningful comparison:
- Use the same task parameters across runs.
- Restart the system between experiments when possible.

---

## Polling Interval Experiment

For both demos, repeat the experiment using different polling intervals.

### Polling interval: **150 ms**

What to observe:
- High number of HTTP requests per client
- Increased server CPU usage due to frequent polling
- Higher cumulative delivery latency
- Streaming mode remains efficient with lower server overhead

This configuration highlights how aggressive polling amplifies server-side cost,
even when responses are small.

---

### Polling interval: **500 ms**

What to observe:
- Fewer HTTP requests and reduced polling overhead
- Noticeable lag in status and result updates on the client
- Less responsive and less smooth progress reporting
- Streaming mode continues to deliver updates with low perceived latency

This configuration makes the **responsiveness vs efficiency tradeoff** of polling
clearly visible.

---

## Task-Specific Parameters

### Compute Pi

- The number of digits to compute can be configured before starting the task.
- Increasing the digit count increases task duration and the number of progress updates.
- Five clients are run simultaneously, all requesting progress for the same task.

This task produces frequent updates and is useful for observing steady update delivery.

---

### Document Analysis

- By default, the demo uses *Metamorphosis* by Franz Kafka.
- The document source URL can be changed to any publicly accessible text resource.
- The set of keywords to search for can be modified before starting the task.

This task produces irregular, bursty updates and highlights polling inefficiencies
during idle periods.

---

## Metrics to Focus On

When comparing streaming and polling modes, focus on:

- **Server CPU usage**  
  Indicates request handling and message delivery overhead.

- **Cumulative delivery latency**  
  Represents the total cost of delivering all updates.

- **Perceived client lag**  
  Observe how quickly progress and results appear on screen.

- **Request or message counts**  
  Highlights amplification effects in polling-based delivery.

---

## Interpretation Guidelines

- Lower polling intervals improve responsiveness but significantly increase server cost.
- Higher polling intervals reduce load but degrade user experience.
- Event-driven streaming avoids this tradeoff by decoupling update production from client requests.

The demos are intended to make these tradeoffs visible and easy to reason about.
