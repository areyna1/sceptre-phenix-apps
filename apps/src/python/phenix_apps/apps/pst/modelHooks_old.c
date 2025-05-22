#include "modelHooks.h"

/* MEX function - IO to MATLAB*/
void mexFunction(int nlhs, mxArray* plhs[], int nrhs, const mxArray* prhs[])
{
  int subroutineNum = mxGetScalar(prhs[0]);
  mxArray* points;
  if (mxIsStruct(prhs[1])) {
	mxArray* points = mxDuplicateArray(prhs[1]);
	subroutine(subroutineNum, points);
	//everything works as pass by ref to update points, except we have to pass by value back to matlab
	plhs[0] = points;
  }
  else {
	mexPrintf("Error: input is not a struct");
	exit(0);
  }
}

void subroutine(int num, mxArray *points)
{
	if(num == 0){
		init();
	}
	else if(num == 1){
		step(points);
	}
	else{
		term();
	}
}

/* **********************************
 * Model Hooks (called from Simulink)
 ********************************** */
void init()
{
  setbuf(stdout, NULL); /* Disable stdout buffering */

  if (-1 != access(DEBUG_FILE, F_OK)) {
    DEBUG = true;
  }
  if (-1 != access(DEBUG_VERBOSE_FILE, F_OK)) {
    DEBUG = true;
    DEBUG_VERBOSE = true;
  }

  printf("Info: Model initialization hooked\n");

  numPublishPoints = 128;
  readFileToMemory(PUBLISH_POINTS_FILE, &publishPoints, &numPublishPoints);
  
  printf("Info: Read %d PublishPoints\n", numPublishPoints);

  /* Create a semaphores in the locked state (last arg = 0)*/
  publishSemaphore = sem_open(PUBLISH_SEM, O_CREAT, 0644, 0);
  if(SEM_FAILED == publishSemaphore) {
    printf("Fatal: Unable to create publish semaphore\n");
    exit(EXIT_ERROR);
  }
  updatesSemaphore = sem_open(UPDATES_SEM, O_CREAT, 0644, 0);
  if(SEM_FAILED == updatesSemaphore) {
    printf("Fatal: Unable to create updates semaphore\n");
    exit(EXIT_ERROR);
  }

  /* Create a FIFO queue for passing UpdatePoints from provider to solver */
  unlink(UPDATES_FIFO); /* just incase fifo still exists from last run */
  if (-1 == mkfifo(UPDATES_FIFO, 0666)) {
    printf("Fatal: Unable to create update FIFO at %s\n", UPDATES_FIFO);
    exit(EXIT_ERROR);
  }
  updatesFifo = open(UPDATES_FIFO, O_RDONLY | O_TRUNC | O_NONBLOCK);
  if (-1 == updatesFifo) {
    printf("Fatal: Unable to open updates FIFO at %s for non-blocked reading\n", UPDATES_FIFO);
    exit(EXIT_ERROR);
  }

  /* Shared Memory Count Blocks */
  numPublishPointsShmId = createSharedMemory(NUM_PUBLISH_POINTS_SHM_KEY, sizeof(unsigned int));
  numPublishPointsShmAddress = attachSharedMemory(numPublishPointsShmId);
  sprintf(numPublishPointsShmAddress, "%u", numPublishPoints);

  /* Shared Memory Blocks */
  publishPointsShmSize = numPublishPoints * MAX_MSG_LEN;
  publishPointsShmId = createSharedMemory(PUBLISH_POINTS_SHM_KEY, publishPointsShmSize);
  publishPointsShmAddress = attachSharedMemory(publishPointsShmId);
  //publishState();

  /* Unlock semaphores */
  sem_post(publishSemaphore);
  sem_post(updatesSemaphore);
}


void step(mxArray *points)
{
  sem_wait(publishSemaphore);
  publishState(points);
  sem_post(publishSemaphore);

  sem_wait(updatesSemaphore);
  applyUpdates(points);
  sem_post(updatesSemaphore);

  fflush(stdout);
}

void term()
{
  /* NOTE: This never gets called if you ^c out of the solver */
  int i;

  printf("Info: Model termination hooked\n");

  sem_wait(publishSemaphore);
  sem_wait(updatesSemaphore);

  destroySharedMemory(numPublishPointsShmId, numPublishPointsShmAddress);
  destroySharedMemory(publishPointsShmId, publishPointsShmAddress);

  sem_close(publishSemaphore);
  sem_unlink(PUBLISH_SEM);

  sem_close(updatesSemaphore);
  sem_unlink(UPDATES_SEM);

  close(updatesFifo);
  unlink(UPDATES_FIFO);

  for (i = 0; i < numPublishPoints; i++) {
    if (NULL != publishPoints[i]) {
      free(publishPoints[i]);
    }
  }
  if (NULL != publishPoints) {
    free(publishPoints);
  }
}



/* *******************************
 * Start Model Interaction Helpers
 ******************************* */
void publishState(mxArray *points)
{
  int i;
  char* shmPtr = publishPointsShmAddress;
  
  for (i = 0; i <numPublishPoints; i++) {
    char* dto = getModelSignalValue(points, publishPoints[i]);
    strcpy(shmPtr, dto);
    shmPtr += MAX_MSG_LEN;

    //printf("Info: Publishing %s\n", dto);

    //dto Memory is allocated in getModelSignalValue
    if (NULL != dto) {
      free(dto);
    }
  }
}

char* getModelSignalValue(mxArray* points, const char* match)
{
    char* dto = (char*)calloc(MAX_MSG_LEN, sizeof(char));
    char* dtoPtr = dto;
    if (NULL == dto) {
      printf("Fatal: Not enough memory for next dto allocation\n");
      exit(EXIT_ERROR);
    }
    dtoPtr += sprintf(dtoPtr, "%s:", match);
    if (DEBUG_VERBOSE) {
	printf("Debug: %s:i\n", match);
    }
    //TODO this is ugly but works for now
    char matchCpy[500];
    strcpy(matchCpy, match);
    
    // Get the tag and field
    char* tag = strtok(matchCpy, ".");
    if (tag == NULL) {
       printf("Fatal: invalid publish point name\n");
       exit(EXIT_ERROR);
    }
    char* field = strtok(0, ".");
   
    //TODO this is ugly
    // get index number from tag
    int index_start = strcspn(tag, "0123456789");
    int index_end = strlen(tag);
    int index_size = index_end-index_start;
    char index_str[index_size+1];
    strncpy(index_str, tag+index_start, index_size);
    index_str[index_size] = '\0'; 
    //The current data structure has inputs first under the "pmus" field then the actual field name
    //note: the index of mxGetField does not correlate to the index we want. We always get the data using index 0 then index from that results. 
    //TODO - make sure either field matches fields from PST or we include if statements here to translate between PST tags and publish points
    double* data_array = mxGetPr(mxGetField(mxGetField(points, 0, "pmus"), 0, field));
    dtoPtr += sprintf(dtoPtr, "DOUBLE:%f", data_array[atoi(index_str)-1]);
    
    return dto;
}

void applyUpdates(mxArray* points)
{
  char *tag, *type, *val;
  char *updateMessage = (char*)calloc(MAX_MSG_LEN, sizeof(char));
  if (NULL == updateMessage) {
    printf("Fatal: Not enough memory for updateMessage allocation\n");
    exit(EXIT_ERROR);
  }

  while (read(updatesFifo, updateMessage, MAX_MSG_LEN) > 0) {
    tag = strtok(updateMessage, ":");
    type = strtok(NULL, ":");
    val = strtok(NULL, ":");

    if (DEBUG) {
      printf("updating tag: %s, type: %s, val: %s\n", tag, type, val);
    }

    updateModelParameterValue(points, tag, val);

    memset(updateMessage, 0, (MAX_MSG_LEN * sizeof(char)));
  }

  if (NULL != updateMessage) {
    free(updateMessage);
  }
}

void updateModelParameterValue(mxArray* points, const char* match, char* newValue)
{
  printf("DEBUG: modelHooks.c UpdateModelParameterValue: %s, %s\n", match, newValue);
  // Get the tag and field
  char* tag = strtok(match, ".");
  if (tag == NULL) {
     printf("Fatal: invalid publish point name\n");
     exit(EXIT_ERROR);
  }
  char* field = strtok(0, ".");
  //TODO this is ugly
  // get index number from tag
  int index_start = strcspn(tag, "0123456789");
  int index_end = strlen(tag);
  int index_size = index_end-index_start;
  char index_str[index_size+1];
  strncpy(index_str, tag+index_start, index_size);
  index_str[index_size] = '\0';       
  //The current data structure has outputs first under the "raas" field then the actual field name
  //note: the index of mxGetField does not correlate to the index we want. We always get the data using index 0 then index from that results. 
  //TODO some error checking would be nice to make sure field is same as what is coming from pst
  double* data_array = mxGetPr(mxGetField(mxGetField(points, 0, "rass"), 0, field));
  data_array[atoi(index_str)-1] = strtod(newValue, NULL);
  
}



/* ***************************
 * Start Shared Memory Helpers
 *************************** */
int createSharedMemory(key_t key, int bytes)
{
  int shmid = shmget(key, bytes, IPC_CREAT | 0666);
  if (shmid < 0) {
    printf("Fatal: Failed to get shared memory for key %d\n", key);
    exit(EXIT_ERROR);
  }

  printf("Info: Created shared memory with key %d\n", key);
  return shmid;
}


char* attachSharedMemory(int shmid)
{
  char *mem = (char*)shmat(shmid, NULL, 0);
  if (mem == (char*)-1){
    printf("Fatal: Failed to attach to shared memory\n");
    exit(EXIT_ERROR);
  }

  printf("Info: Attached to shared memory\n");
  return mem;
}


void destroySharedMemory(int shmid, char* shmaddr)
{
  shmdt(shmaddr);
  shmctl(shmid, IPC_RMID, NULL);

  printf("Info: Destroyed shared memory\n");
}



/* *******************
 * Start Misc. Helpers
 ******************* */
void readFileToMemory(const char* fileName, char** *array, unsigned int *num)
{
  FILE* fp = NULL;
  size_t lineLen = 0;
  ssize_t bytesRead = 0;
  int linesRead = 0;
  int k;

  fp = fopen(fileName, "r");
  if (NULL == fp) {
    printf("Fatal: Cannot open/find file: %s\n", fileName);
    exit(EXIT_ERROR);
  }

  *array = (char **)malloc(sizeof(char*) * (*num));
  if (NULL == *array) {
    printf("Fatal: Cannot allocate space for memory array\n");
    exit(EXIT_ERROR);
  }

  for (k = 0; k < *num; k++) {
    (*array)[k] = (char*)malloc(sizeof(char*) * MAX_MSG_LEN);;
    if (NULL == (*array)[k]) {
      printf("Fatal: Cannot allocate space for memory subarray\n");
      exit(EXIT_ERROR);
    }
  }

  while ((bytesRead = getline(&(*array)[linesRead], &lineLen, fp)) != -1) {
    if (linesRead >= *num) {
      /* Allocate more space in the array */
      *num = *num * 2;
      *array = (char **)realloc(*array, sizeof(char*) * *num);
      if (NULL == *array) {
        printf("Fatal: Cannot re-allocate space for more memory");
        exit(EXIT_ERROR);
      }
    }

    (*array)[linesRead][bytesRead-1] = 0; /*remove newline character*/

    linesRead++;
  }

  *num = linesRead;

  fclose(fp);
}

void printModelMemberCounts()
{
  /*uint_T numModelParams = rtwCAPI_GetNumModelParameters(modelMap);
  uint_T numBlockParams = rtwCAPI_GetNumBlockParameters(modelMap);
  uint_T numStates = rtwCAPI_GetNumStates(modelMap);
  uint_T numModelSignals = rtwCAPI_GetNumSignals(modelMap);

  printf("Number of Model Parameters %d\n", numModelParams);
  printf("Number of Block Parameters %d\n", numBlockParams);
  printf("Number of States %d\n", numStates);
  printf("Number of Signals %d\n", numModelSignals);
  */
}

